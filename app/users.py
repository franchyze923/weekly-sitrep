"""Manage built-in users.

    python -m app.users add <email> [--name "Full Name"]     prompts for password
    python -m app.users passwd <email>                         prompts for new password
    python -m app.users list
    python -m app.users disable <email> | enable <email>
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from . import auth, db


def _get(s, email):
    user = s.scalar(select(db.User).where(db.User.email == email.lower()))
    if user is None:
        sys.exit("No user {}".format(email))
    return user


def _prompt_password():
    pw = getpass.getpass("Password: ")
    if len(pw) < 8:
        sys.exit("Password must be at least 8 characters.")
    if pw != getpass.getpass("Again: "):
        sys.exit("Passwords did not match.")
    return pw


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m app.users")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("email"); a.add_argument("--name", default="")
    a.add_argument("--password", help="non-interactive; otherwise prompted")
    p = sub.add_parser("passwd"); p.add_argument("email"); p.add_argument("--password")
    sub.add_parser("list")
    sub.add_parser("disable").add_argument("email")
    sub.add_parser("enable").add_argument("email")
    args = ap.parse_args(argv)

    db.Base.metadata.create_all(db.engine)
    with db.SessionLocal() as s:
        if args.cmd == "add":
            email = args.email.lower()
            if s.scalar(select(db.User).where(db.User.email == email)):
                sys.exit("User {} already exists.".format(email))
            pw = args.password or _prompt_password()
            s.add(db.User(email=email, name=args.name or email, password_hash=auth.hash_password(pw)))
            s.commit(); print("Added", email)
        elif args.cmd == "passwd":
            user = _get(s, args.email)
            user.password_hash = auth.hash_password(args.password or _prompt_password())
            s.commit(); print("Password updated for", user.email)
        elif args.cmd == "list":
            for u in s.scalars(select(db.User).order_by(db.User.email)):
                print("{:<40} {:<30} {}".format(u.email, u.name, "active" if u.active else "disabled"))
        else:
            user = _get(s, args.email)
            user.active = args.cmd == "enable"
            s.commit(); print(user.email, "is now", "active" if user.active else "disabled")


if __name__ == "__main__":
    main()
