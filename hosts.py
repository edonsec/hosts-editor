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
    def __init__(self, domain, ipaddr, raw, active=False, idx=None):
        self.domain = domain
        self.ipaddr = ipaddr
        self.active = active
        self.idx = idx
        self.raw = raw


class HostProfileManager(object):
    DEFAULT_NAME = "default"

    def __init__(self, path, host_file):
        self._path = path
        self._host_file = host_file

    def switch(self, name, fresh=False):
        profile_path = self.add(name, fresh)

        if os.path.exists(self._host_file):
            os.unlink(self._host_file)
            os.symlink(profile_path, self._host_file)

    def remove(self, name):
        profile_path = self.get_profile_path(name)

        if os.path.exists(profile_path):
            self.switch(self.DEFAULT_NAME)
            os.unlink(profile_path)

    def add(self, name, fresh=False):
        default_path = self.get_profile_path(self.DEFAULT_NAME)
        profile_path = self.get_profile_path(name)

        if not os.path.exists(profile_path):
            if fresh:
                open(profile_path, "w").close()
            else:
                copyfile(default_path, profile_path)

        return profile_path

    def get_active_profile(self):
        if os.path.islink(self._host_file):
            return os.path.realpath(self._host_file).rsplit(".")[-1]

    def get_profile_path(self, name):
        return "{}/hosts.{}".format(self._path, name)

    def get_path(self):
        return self._path


class FileEditor(object):
    def __init__(self, path):
        self._path = path
        self._delete = []
        self._edit = []

    def edit_line(self, line, value):
        self._edit.append([line, value])

        return self

    def delete_line(self, line):
        self._delete.append(line)

        return self

    def _get_edit_for_line(self, line_no):
        for edit_line, edit_value in self._edit:
            if line_no == edit_line:
                return edit_value

    def write(self):
        with open(self._path, "r+") as f:
            lines = f.readlines()
            f.seek(0)
            for line_no, line in enumerate(lines):
                edit_value = self._get_edit_for_line(line_no)

                if edit_value:
                    f.write(edit_value)
                    continue

                if line_no not in self._delete:
                    f.write(line)

            f.truncate()

        self._reset()

    def _reset(self):
        self._delete = []
        self._edit = []


class HostFileManager(object):
    HOST_FILE_PATH = "/etc/hosts"
    DEFAULT_PROFILE = "default"

    def __init__(self, editor, parser_, profile_manager):
        self._profile_path = profile_manager.get_path()
        self._parser = parser_
        self._profile_manager = profile_manager
        self._editor = editor

    def setup(self):
        default_profile_path = self._profile_manager.get_profile_path(
            self.DEFAULT_PROFILE)

        if not os.path.exists(self._profile_path):
            os.mkdir(self._profile_path)
            copyfile(self.HOST_FILE_PATH, default_profile_path)

        if not os.path.islink(self.HOST_FILE_PATH):
            move(self.HOST_FILE_PATH, self.HOST_FILE_PATH + ".default")
            os.symlink(default_profile_path, self.HOST_FILE_PATH)

    def get_profiles(self):
        return [fname.rsplit(".")[-1] for fname in os.listdir(self._profile_path)]

    def get_entries(self, search=None):
        for host in self._parser.get_entries():
            if not search or (search and host.domain.startswith(search)):
                yield host

    def get_active_profile(self):
        if os.path.islink(self.HOST_FILE_PATH):
            return os.path.realpath(self.HOST_FILE_PATH).rsplit(".")[-1]

    def create_entry(self, domain, ip_address):
        with open(self.HOST_FILE_PATH, "a+") as f:
            f.write("{} {}\n".format(ip_address, domain))

    def remove_entry_by_domain(self, domain):
        self.find_entry(domain, self.__remove_line)

    def __remove_line(self, entry):
        self._editor.delete_line(entry.idx).write()

    def toggle_entry_by_domain(self, domain):
        self.find_entry(domain, self._toggle_commented_line)

    def _toggle_commented_line(self, entry):
        edit = "#{}".format(entry.raw) if entry.active else entry.raw[1:]
        self._editor.edit_line(entry.idx, edit).write()

    def find_entry(self, domain, callback):
        for entry in self.get_entries():
            if entry.domain == domain:
                if callback:
                    callback(entry)

    def is_matched_domain(self, domain, subject):
        return domain == subject or subject == "#{}".format(domain)


class HostFileParser(object):
    def __init__(self, path):
        self.path = path

    def get_entries(self):
        with open(self.path) as f:
            for idx, line in enumerate(f.readlines()):
                entry = re.split("\s", line)

                if not self.valid_host_entry(entry):
                    continue

                active = not self.is_comment(entry[0])
                yield HostEntry(entry[1], self.strip_comment(entry[0]), line, active, idx=idx)

    def strip_comment(self, line):
        return line[1:] if line[0] == "#" else line

    def is_comment(self, line):
        return line[0] == "#"

    def valid_host_entry(self, parts):
        if len(parts) < 2:
            return False

        return (
            re.match("^#?[\d:.]+$", parts[0])
            and re.match("^[a-z0-9-.]+$", parts[1])
        )


class HostShell(cmd.Cmd):
    intro = "Welcome to the Hosts editor shell. " \
            "Type help or ? to list commands.\n"
    prompt = "hosts> "
    file = None

    def __init__(self, file_manager, profile_manager):
        cmd.Cmd.__init__(self)
        self._file_manager = file_manager
        self._profile_manager = profile_manager
        self._profiles = file_manager.get_profiles()

    def do_remove(self, domain):
        if not domain:
            self.onecmd("help remove")
            return

        self._file_manager.remove_entry_by_domain(domain)

    def complete_remove(self, text, line, begidx, endidx):
        return [d.domain for d in self._file_manager.get_entries(search=text)]

    def help_remove(self):
        print("remove <domain> - remove an entry to active profile")

    def do_create(self, args):
        argsplit = args.split()
        if len(argsplit) != 2:
            self.onecmd("help create")
            return

        self._file_manager.create_entry(argsplit[0], argsplit[1])

    def help_create(self):
        print("create <domain> <ip address> - create an entry on active profile")

    def do_update(self, args):
        argsplit = args.split()

        if not args or len(argsplit) != 2:
            self.onecmd("help update")
            return

        self._file_manager.remove_entry_by_domain(argsplit[0])
        self._file_manager.create_entry(argsplit[0], argsplit[1])

    def help_update(self):
        print("update <domain> <ip address> - update an existing entry in active profile")

    def do_toggle(self, domain):
        if not domain:
            self.onecmd("help toggle")
            return

        self._file_manager.toggle_entry_by_domain(domain)

    def complete_toggle(self, text, line, begidx, endidx):
        return [d.domain for d in self._file_manager.get_entries(search=text)]

    def help_toggle(self):
        print("toggle <domain> - toggle enabled status in hosts file")

    def do_show(self, type):
        if type in ["profiles", "hosts"]:
            self.onecmd(type)
        else:
            self.onecmd("help show")

    def complete_show(self, text, line, begidx, endidx):
        show_types = ["profiles", "hosts"]
        show = [type for type in show_types if type.startswith(text)]

        return show if show else show_types

    def help_show(self):
        print("show profiles|hosts - Display either the present profiles or the lists of hosts in a given profile")

    def do_profiles(self, args):
        for profile in self._file_manager.get_profiles():
            print("* {}".format(profile))

    def help_profiles(self):
        print("profiles - Show list of profiles")

    def do_hosts(self, args):
        for host in self._file_manager.get_entries():
            print("[{}] {} => {}".format("ACTIVE" if host.active else "INACTIVE", host.domain, host.ipaddr))

    def help_hosts(self):
        print("hosts - Show list of hosts")

    def do_profile(self, args):
        argsplit = args.split()
        status = False

        if len(argsplit) == 1:
            args = argsplit[0]
        elif len(argsplit) == 2:
            args, status = argsplit
        else:
            self.onecmd("help profile")

        commands = {
            "remove": self._do_profile_remove,
            "fresh": self._do_profile_fresh,
            "default": self._do_profile_switch
        }

        commands.get(status, commands["default"])(args)

    def complete_profile(self, text, line, begidx, endidx):
        profile_entries = self._file_manager.get_profiles()
        profile_actions = ["remove", "fresh"]

        profiles = [p for p in profile_entries if p.startswith(text)]

        if line.count(" ") == 2:
            actions = [a for a in profile_actions if a.startswith(text)]

            return actions if actions else profile_actions

        return profiles if profiles else profile_entries

    def help_profile(self):
        print("profile <name> [remove|fresh] - Profile management, switch, remove and create new")

    def do_exit(self, args):
        raise ExitShell

    def help_exit(self):
        print("Quit from shell")

    def set_prompt_name(self, name):
        self.prompt = "hosts/{}> ".format(name)

    def _do_profile_remove(self, name):
        self._profile_manager.remove(name)
        self.set_prompt_name("default")

    def _do_profile_fresh(self, name):
        self._profile_manager.switch(name, fresh=True)
        self.set_prompt_name(name)

    def _do_profile_switch(self, name):
        self._profile_manager.switch(name)
        self.set_prompt_name(name)

    do_quit = do_exit
    do_EOF = do_exit


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("This script must be run as root")
        sys.exit()

    parser = argparse.ArgumentParser()

    try:
        parser.add_argument("--profile", "-p", help="Specify profile", metavar=("PROFILE"))
        parser.add_argument("--create", "-c", nargs=2, help="Create host entry; Args: <domain> <ip address>",
                            metavar=("DOMAIN", "IP_ADDRESS"))
        parser.add_argument("--remove", "-r", help="Remove host entry by domain", metavar=("DOMAIN"))
        parser.add_argument("--update", "-u", nargs=2, help="Update existing host entry",
                            metavar=("DOMAIN", "IP_ADDRESS"))
        parser.add_argument("--toggle", "-t", help="Toggle host entry by domain", metavar=("DOMAIN"))
        parser.add_argument("--show", "-s", help="Show hosts or profiles", choices=["hosts", "profiles"])
        parser.add_argument("--interactive", "-i", help="Interactive mode", action='store_const', const=True)

        args = parser.parse_args()
        has_arg_set = [k for k in args.__dict__ if args.__dict__[k] is not None]

        if not has_arg_set:
            parser.print_help()
            sys.exit(0)

        hostManagerPath = "/etc/hosts-editor"
        hostFileParser = HostFileParser(HostFileManager.HOST_FILE_PATH)
        hostFileEditor = FileEditor(HostFileManager.HOST_FILE_PATH)
        hostProfileManager = HostProfileManager(hostManagerPath, HostFileManager.HOST_FILE_PATH)

        hostFileManager = HostFileManager(hostFileEditor, hostFileParser, hostProfileManager)
        hostFileManager.setup()

        hostShell = HostShell(hostFileManager, hostProfileManager)
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
