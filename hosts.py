#!/usr/bin/env python
import cmd
import os
import sys
import re
from shutil import copyfile, move
import argparse


class ExitShell(Exception):
    pass


class HostEntry(object):
    def __init__(self, domain, ipaddr, active):
        self.domain = domain
        self.ipaddr = ipaddr
        self.active = active


class HostFileManager(object):
    HOST_FILE_PATH = "/etc/hosts"
    DEFAULT_PROFILE = "default"

    base_dir = ""

    def __init__(self, base_dir):
        self.base_dir = base_dir

    def setup(self):
        default_host_path = self.get_profile_path(self.DEFAULT_PROFILE)

        if not os.path.exists(self.base_dir):
            os.mkdir(self.base_dir)
            copyfile(self.HOST_FILE_PATH, default_host_path)

        if not os.path.islink(self.HOST_FILE_PATH):
            move(self.HOST_FILE_PATH, self.HOST_FILE_PATH + ".default")
            os.symlink(default_host_path, self.HOST_FILE_PATH)

    def get_profiles(self):
        return [fname.rsplit(".")[-1] for fname in os.listdir(self.base_dir)]

    def get_entries(self, search=None):
        entries = []
        with open(self.HOST_FILE_PATH) as f:
            for line in f.readlines():
                parts = re.split("\s+", line)

                if not self.valid_host_entry(parts):
                    continue

                if not search or (search and domain.startswith(search)):
                    ipaddr_stripped = parts[0].replace("#", "")
                    active = True if parts[0][0] != "#" else False
                    entries.append(HostEntry(parts[1], ipaddr_stripped, active))

        return entries

    def valid_host_entry(self, parts):
        if len(parts) < 2:
            return False

        return (
            re.match("^#?[\d:.]+$", parts[0])
            and re.match("^[a-z0-9-.]+$", parts[1])
        )

    def get_active_profile(self):
        if os.path.islink(self.HOST_FILE_PATH):
            return os.path.realpath(self.HOST_FILE_PATH).rsplit(".")[-1]

    def create_entry(self, domain, ip_address):
        with open(self.HOST_FILE_PATH, "a+") as f:
            f.write("{} {}\n".format(ip_address, domain))

    def remove_entry_by_domain(self, domain):
        self.find_entry(domain, None)

    def toggle_entry_by_domain(self, domain):
        self.find_entry(domain, self.toggle_commented_line)

    def toggle_commented_line(self, entry, fp):
        if not entry.startswith("#"):
            fp.write("#" + entry)
        else:
            fp.write(entry[1:])

    def switch_profile(self, name, fresh=False):
        default_path = self.get_profile_path(self.DEFAULT_PROFILE)
        profile_path = self.get_profile_path(name)

        if not os.path.exists(profile_path):
            if fresh:
                open(profile_path, "w").close()
            else:
                copyfile(default_path, profile_path)

        if os.path.exists(self.HOST_FILE_PATH):
            os.unlink(self.HOST_FILE_PATH)
            os.symlink(profile_path, self.HOST_FILE_PATH)

    def remove_profile(self, name):
        profile_path = self.get_profile_path(name)

        if os.path.exists(profile_path):
            self.switch_profile("default")
            os.unlink(profile_path)

    def find_entry(self, domain, callback):
        with open(self.HOST_FILE_PATH, "r+") as f:
            lines = f.readlines()
            f.seek(0)
            for line in lines:
                entry = re.split("\s", line)

                if entry[1] == domain or entry[1] == "#{}".format(domain):
                    if callback:
                        callback(line, f)
                else:
                    f.write(line)

            f.truncate()

    def get_profile_path(self, name):
        return "{}/hosts.{}".format(self.base_dir, name)


class HostShell(cmd.Cmd):
    intro = "Welcome to the Hosts editor shell. " \
            "Type help or ? to list commands.\n"
    prompt = "hosts> "
    file = None
    hostFileManager = None
    profiles = []

    def __init__(self, hostFileManager):
        cmd.Cmd.__init__(self)
        self.hostFileManager = hostFileManager
        self.profiles = hostFileManager.get_profiles()

    def do_remove(self, domain):
        """remove <domain> - remove an entry to active profile"""
        self.hostFileManager.remove_entry_by_domain(domain)

    def complete_remove(self, text, line, begidx, endidx):
        return [d.domain for d in self.hostFileManager.get_entries(search=text)]

    def do_create(self, args):
        """create <domain> <ip address> - create an entry on active profile"""
        args = args.split()
        if len(args) != 2:
            self.onecmd("help create")

        self.hostFileManager.create_entry(args[0], args[1])

    def do_update(self, args):
        """update <domain> <ip address> - update an existing entry in active profile"""
        args = args.split()
        if len(args) != 2:
            self.onecmd("help update")

        self.hostFileManager.remove_entry_by_domain(args[0])
        self.hostFileManager.create_entry(args[0], args[1])

    def do_toggle(self, domain):
        """toggle <domain> - toggle enabled status in hosts file"""
        self.hostFileManager.toggle_entry_by_domain(domain)

    def complete_toggle(self, text, line, begidx, endidx):
        return [d.domain for d in self.hostFileManager.get_entries(search=text)]

    def do_show(self, type):
        """show profiles|hosts - Display either the present profiles or the lists of hosts in a given profile"""
        if type in ["profiles", "hosts"]:
            self.onecmd(type)

    def complete_show(self, text, line, begidx, endidx):
        show_types = ["profiles", "hosts"]
        show = [type for type in show_types if type.startswith(text)]

        return show if show else show_types

    def do_profiles(self, args):
        """profiles - Show list of profiles"""
        for profile in self.hostFileManager.get_profiles():
            print "* {}".format(profile)

    def do_hosts(self, args):
        """hosts - Show list of hosts"""
        for host in self.hostFileManager.get_entries():
            print "[{}] {} => {}".format("ACTIVE" if host.active else "INACTIVE", host.domain, host.ipaddr)

    def do_profile(self, name):
        """profile <name> [remove|fresh] - Switch to a separate host profile (fresh starts as empty) or delete an existing one"""
        args = name.split()
        status = False

        if len(args) == 1:
            name = args[0]
        elif len(args) == 2:
            name, status = args
        else:
            self.onecmd("help profile")

        if status == "remove":
            self.hostFileManager.remove_profile(name)
            self.set_prompt_name("default")
        elif status == "fresh":
            self.hostFileManager.switch_profile(name, fresh=True)
            self.set_prompt_name(name)
        else:
            self.hostFileManager.switch_profile(name)
            self.set_prompt_name(name)

    def complete_profile(self, text, line, begidx, endidx):
        profile_entries = self.hostFileManager.get_profiles()
        profile_actions = ["remove", "fresh"]

        profiles = [p for p in profile_entries if p.startswith(text)]

        if line.count(" ") == 2:
            actions = [a for a in profile_actions if a.startswith(text)]

            return actions if actions else profile_actions

        return profiles if profiles else profile_entries

    def do_exit(self, args):
        'Quit from shell'
        raise ExitShell

    def set_prompt_name(self, name):
        self.prompt = "hosts/{}> ".format(name)

    do_quit = do_exit
    do_EOF = do_exit


if __name__ == "__main__":
    if os.geteuid() != 0:
        print "This script must be run as root"
        sys.exit()

    parser = argparse.ArgumentParser()

    try:
        parser.add_argument("--profile", "-p", help="Specify profile", metavar=("PROFILE"))
        parser.add_argument("--create", "-c", nargs=2, help="Create host entry; Args: <domain> <ip address>", metavar=("DOMAIN", "IP_ADDRESS"))
        parser.add_argument("--remove", "-r", help="Remove host entry by domain", metavar=("DOMAIN"))
        parser.add_argument("--update", "-u", nargs=2, help="Update existing host entry", metavar=("DOMAIN", "IP_ADDRESS"))
        parser.add_argument("--toggle", "-t", help="Toggle host entry by domain", metavar=("DOMAIN"))
        parser.add_argument("--show", "-s", help="Show hosts or profiles", choices=["hosts", "profiles"])
        parser.add_argument("--interactive", "-i", help="Interactive mode", action='store_const', const=True)

        args = parser.parse_args()
        has_arg_set = [k for k in args.__dict__ if args.__dict__[k] is not None]

        if not has_arg_set:
            parser.print_help()
            sys.exit(0)

        hostFileManager = HostFileManager("/etc/hosts-editor")
        hostFileManager.setup()

        hostShell = HostShell(hostFileManager)
        hostShell.set_prompt_name(hostFileManager.get_active_profile())

        if not args.interactive:
            if args.profile:
                hostShell.onecmd("profile " + args.profile)

            if args.create:
                hostShell.onecmd("create " + " ".join(args.create))

            if args.toggle:
                hostShell.onecmd("toggle " + args.toggle)

            if args.remove:
                hostShell.onecmd("remove " + args.remove)

            if args.show:
                hostShell.onecmd("show " + args.show)

            if args.update:
                hostShell.onecmd("update " + " ".join(args.update))
        else:
            hostShell.cmdloop()

    except ExitShell:
        pass
