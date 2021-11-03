swaj
====

"If you watch the movie Jaws backwards, it's a movie about a shark that keeps
throwing up people until they have to open a beach."

`swaj` is a tool to simplify using multiple sets of credentials with AWS. If
you have multiple profiles, `swaj` eliminates the need to constantly re-export
values when using MFA or SSO. `swaj` is especially helpful when using MFA in
that it persists the temporary session credentials, minimizing the number of
times an OTP code must be entered.

Requires python.

If you'd like to use the built-in TOTP functionality (instead of an app, like
Google Authenticator or Authy), you'll also need to install pyotp, like so:
`pip install pyotp`.

Install
=======

```!sh
$ curl https://raw.githubusercontent.com/f0rk/swaj/master/tools/swaj-standalone > ~/bin/swaj
$ chmod +x ~/bin/swaj
```

Configuration
=============

If you wish to use swaj to more safely use profiles, no additional
configuration is needed.

If you wish to use an MFA device (currently, the AWS API only supports
software-based devices), place the serial of that device in your
`~/.aws/config` like so:

```
[profile dev]
region = us-west-1
mfa_serial = arn:aws:iam::000000000000:mfa/jimmy
```

Additionally, if you wish to assume a role, you can configure it like so:
```
[profile admin]
region = us-west-1
mfa_serial = arn:aws:iam::000000000000:mfa/jimmy
swaj_role_arn = arn:aws:iam::000000000000:role/admin
```

This usage is non-standard but is a workaround for a bug in botocore.

Using SSO is straightforward, just configure your SSO normally and `swaj` will
ensure you are authenticated.

Usage
=====

`swaj` works with profiles as defined in your `~/.aws/config`. It does not
support other modes of operation. You must either set `AWS_PROFILE` in your
environment or pass `--profile yourprofile` to it.

`swaj` will get everything squared away with MFA and then run your command with
the determiend credentials:

```
$ swaj --profile dev exec aws s3api list-buckets               
enter token for mfa_serial arn:aws:iam::000000000000:mfa/jimmy: 123456  
{                                                     
    "Buckets": [
        {
            "Name": "bananaphone",            
            "CreationDate": "2020-05-08T01:01:01.000Z"
        },
    ],
    "Owner": {
        "DisplayName": "jimmysworld",
        "ID": "0000000000000000000000000000000000000000000000000000000000000000"
    }
}
```

Subsequent runs will not prompt you for MFA credentials:
```
$ swaj --profile dev exec aws s3api list-buckets               
{                                                     
    "Buckets": [
        {
            "Name": "bananaphone",            
            "CreationDate": "2020-05-08T01:01:01.000Z"
        },
    ],
    "Owner": {
        "DisplayName": "jimmysworld",
        "ID": "0000000000000000000000000000000000000000000000000000000000000000"
    }
}
```

Perhaps, though, you just want to set the credentials in your environment. To
get the credentials you could run:

```
$ swaj --profile dev env
...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
AWS_ACCESS_KEY_ID=...
AWS_SESSION_EXPIRATION=...
...
```

For convenience, you can use the `eval` subcommand to simplify:

```
$ eval $(swaj --profile dev eval)
$ env | grep AWS
... 
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...
AWS_ACCESS_KEY_ID=...
AWS_SESSION_EXPIRATION=...
...
```
