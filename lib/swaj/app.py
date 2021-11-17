#!/usr/bin/env python

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

import botocore.exceptions
import botocore.session
import botocore.configloader
import botocore.configprovider
import dateutil
import lockfile


def get_aws_vars(bs, profile):

    aws_vars = {}
    for var_name, var_value in os.environ.items():
        if var_name.startswith("AWS_"):
            aws_vars[var_name] = var_value

    credentials = bs.get_credentials()
    aws_vars["AWS_ACCESS_KEY_ID"] = credentials.access_key
    aws_vars["AWS_SECRET_ACCESS_KEY"] = credentials.secret_key
    aws_vars["AWS_SESSION_TOKEN"] = credentials.token

    for key, value in list(aws_vars.items()):
        if value is None:
            del aws_vars[key]

    return aws_vars


def sso_login(profile):
    if sys.stdout.isatty():
        sso_args = [
            "aws",
            "sso",
            "login",
            "--profile",
            profile,
        ]
        sso_login = subprocess.Popen(sso_args)
        sso_login_stdout, sso_login_stderr = sso_login.communicate()

        if sso_login.returncode:
            raise Exception(
                "{} failed: {} {}"
                .format(
                    " ".join(sso_args),
                    sso_login_stdout,
                    sso_login_stderr,
                )
            )
    else:
        sys.stderr.write(
            "not an interactive terminal, unable to run sso login "
            "interactively!\n"
        )
        sys.stderr.flush()
        sys.exit(1)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        help=(
            "profile to use if AWS_PROFILE not set. if AWS_PROFILE is set, this "
            "will override it."
        ),
    )

    subparsers = parser.add_subparsers(dest="command")

    exec_parser = subparsers.add_parser("exec")
    exec_parser.add_argument("command", nargs=argparse.REMAINDER)
    exec_parser.set_defaults(which="exec")

    env_parser = subparsers.add_parser("env")
    env_parser.set_defaults(which="env")

    eval_parser = subparsers.add_parser("eval")
    eval_parser.set_defaults(which="eval")

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.set_defaults(which="refresh")

    args = parser.parse_args()

    profile = os.environ.get("AWS_PROFILE")
    if args.profile is not None:
        profile = args.profile

    if profile is None:
        sys.stderr.write(
            "unable to locate profile, please set AWS_PROFILE or --profile "
            "argument\n"
        )
        sys.stderr.flush()
        sys.exit(1)

    bs = botocore.session.Session(profile=profile)

    try:
        aws_vars = get_aws_vars(bs, profile)
    except botocore.exceptions.SSOTokenLoadError:
        sso_login(profile)
        aws_vars = get_aws_vars(bs, profile)
    except botocore.exceptions.UnauthorizedSSOTokenError:
        sso_login(profile)
        aws_vars = get_aws_vars(bs, profile)

    config_mapping = botocore.configprovider.create_botocore_default_config_mapping(bs)
    config_file = config_mapping["config_file"].provide()

    config = botocore.configloader.multi_file_load_config(config_file)

    profile_config = config.get("profiles", {}).get(profile, {})

    sts_client = bs.create_client("sts")
    original_identity = sts_client.get_caller_identity()
    user_arn = original_identity["Arn"]
    user_name_part = user_arn.split(":")[-1]
    user_name = user_name_part.split("/")[-1]

    def get_state_path():
        return os.path.expanduser("~/.swajdb")

    def get_lock_path():
        return os.path.join(tempfile.gettempdir(), "swaj.lock")

    def load_state():
        state_path = get_state_path()
        if not os.path.exists(state_path):
            return {}
        else:
            with open(state_path, "rt+") as fp:
                return json.load(fp)

    def store_state(state):
        state_path = get_state_path()
        lock_path = get_lock_path()
        lock = lockfile.LockFile(lock_path)

        try:
            lock.acquire(timeout=10)

            with open(state_path, "wt+") as fp:
                os.chmod(state_path, 0o600)

                json.dump(state, fp)

        finally:
            lock.release()

    state = load_state()

    time_format = "%Y-%m-%dT%H:%M:%SZ"
    current_time = datetime.datetime.now(tz=dateutil.tz.tzutc())
    formatted_current_time = current_time.strftime(time_format)

    if "mfa_serial" in profile_config:

        mfa_serial = profile_config["mfa_serial"]

        if args.which == "refresh":
            if mfa_serial in state:
                del state[mfa_serial]

        if mfa_serial in state:
            mfa_serial_expiration = state[mfa_serial]["AWS_SESSION_EXPIRATION"]
            if formatted_current_time > mfa_serial_expiration:
                del state[mfa_serial]

        if mfa_serial in state:
            aws_vars.update(state[mfa_serial])
        else:
            if sys.stdout.isatty():
                token_code = input("enter token for mfa_serial {}: ".format(mfa_serial))
            else:
                sys.stderr.write(
                    "not an interactive terminal, unable to collect token for "
                    "mfa_serial!\n"
                )
                sys.stderr.flush()
                sys.exit(1)

            sts_client = bs.create_client("sts")

            get_session_token_resp = sts_client.get_session_token(
                SerialNumber=mfa_serial,
                TokenCode=token_code,
            )

            aws_vars["AWS_ACCESS_KEY_ID"] = get_session_token_resp["Credentials"]["AccessKeyId"]
            aws_vars["AWS_SECRET_ACCESS_KEY"] = get_session_token_resp["Credentials"]["SecretAccessKey"]
            aws_vars["AWS_SESSION_TOKEN"] = get_session_token_resp["Credentials"]["SessionToken"]
            aws_vars["AWS_SESSION_EXPIRATION"] = get_session_token_resp["Credentials"]["Expiration"].strftime(time_format)

        if mfa_serial not in state:
            state[mfa_serial] = {}

        state[mfa_serial].update(aws_vars)

        store_state(state)

    if "swaj_role_arn" in profile_config:

        role_arn = profile_config["swaj_role_arn"]

        if args.which == "refresh":
            if role_arn in state:
                del state[role_arn]

        if role_arn in state:
            role_arn_expiration = state[role_arn]["AWS_SESSION_EXPIRATION"]
            if formatted_current_time > role_arn_expiration:
                del state[role_arn]

        if role_arn in state:
            aws_vars.update(state[role_arn])
        else:
            sts_client_args = {
                "service_name": "sts",
                "aws_access_key_id": aws_vars["AWS_ACCESS_KEY_ID"],
                "aws_secret_access_key": aws_vars["AWS_SECRET_ACCESS_KEY"],
                "aws_session_token": aws_vars["AWS_SESSION_TOKEN"],
            }

            for key, value in list(sts_client_args.items()):
                if not value:
                    del sts_client_args[key]

            sts_client = bs.create_client(**sts_client_args)

            role_session_name = user_name

            assume_role_resp = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=role_session_name,
            )

            aws_vars["AWS_ACCESS_KEY_ID"] = assume_role_resp["Credentials"]["AccessKeyId"]
            aws_vars["AWS_SECRET_ACCESS_KEY"] = assume_role_resp["Credentials"]["SecretAccessKey"]
            aws_vars["AWS_SESSION_TOKEN"] = assume_role_resp["Credentials"]["SessionToken"]
            aws_vars["AWS_SESSION_EXPIRATION"] = assume_role_resp["Credentials"]["Expiration"].strftime(time_format)

        if role_arn not in state:
            state[role_arn] = {}

        state[role_arn].update(aws_vars)

        store_state(state)

    new_environ = os.environ.copy()
    new_environ.update(aws_vars)
    new_environ["SWAJ"] = "1"
    new_environ["SWAJ_PROFILE"] = profile

    do_remove_profile = False
    if "AWS_PROFILE" in new_environ:
        do_remove_profile = True
        del new_environ["AWS_PROFILE"]

    if args.which == "refresh":
        pass
    elif args.which == "env":
        for key, value in new_environ.items():
            print("{}={}".format(key, value))
    elif args.which == "eval":
        for key, value in new_environ.items():
            if key.startswith("AWS_") or key.startswith("SWAJ_"):
                print("export {}={}".format(key, value))

        if do_remove_profile:
            print("unset AWS_PROFILE")
    elif args.which == "exec":
        if args.command:
            new_command = args.command
        else:
            new_command = [os.environ.get("SHELL", "/bin/sh")]

        exec_path = new_command[0]
        if not "/" in exec_path:
            maybe_exec_path = shutil.which(exec_path)
            if maybe_exec_path:
                exec_path = maybe_exec_path

        os.execve(exec_path, new_command, new_environ)
    else:
        raise Exception(
            "Implementation Error: unknown value for args.which {}"
            .format(args.which)
        )
