#!/usr/bin/env python
import cmd
import os
import sys
import re
from shutil import copyfile, move
import argparse

class ExitShell(Exception):
  pass

class HostEntry():
  domain = ""
  ipaddr = ""
  active = False

  def __init__(self, domain, ipaddr, active):
    self.domain = domain
    self.ipaddr = ipaddr
    self.active = active

class HostFileManager():
  HOST_FILE_PATH = "/etc/hosts"
  HOST_MANAGER_DEFAULT_FILENAME = "hosts.default"

  base_dir = ""

  def __init__(self, base_dir):
    self.base_dir = base_dir
    self.ensure_setup() 

  def ensure_setup(self):
    host_manager_original_path = "{}/{}".format(self.base_dir, self.HOST_MANAGER_DEFAULT_FILENAME)

    if not os.path.exists(self.base_dir):
      os.mkdir(self.base_dir)
      copyfile(self.HOST_FILE_PATH, host_manager_original_path) 
      
    if not os.path.islink(self.HOST_FILE_PATH):
      move(self.HOST_FILE_PATH, self.HOST_FILE_PATH + ".default")
      os.symlink(host_manager_original_path, self.HOST_FILE_PATH)

  def get_profiles(self):
    entries = []
    for fname in os.listdir(self.base_dir):
      entries.append(fname.rsplit(".")[-1])

    return entries

  def get_entries(self, search=None):
    entries = []
    with open(self.HOST_FILE_PATH) as f:
      for line in f.readlines():
        parts = re.split("\s+", line)

        if len(parts) == 2 or not self.valid_host_entry(parts[0], parts[1]): continue

        if not search or (search and parts[1].startswith(search)):
          entries.append(HostEntry(parts[1], parts[0].replace("#", ""), True if line[0] != "#" else False))

    return entries

  def valid_host_entry(self, ipaddr, domain):
    return re.match("^#?[\d:.]+$", ipaddr) and re.match("^[a-z0-9-.]+$", domain)

  def get_active_profile(self):
    if os.path.islink(self.HOST_FILE_PATH):
      return os.path.realpath(self.HOST_FILE_PATH).rsplit(".")[-1]

  def create_entry(self, domain, ip_address):
    with open(self.HOST_FILE_PATH, "a+") as f:
      f.write("{} {}\n".format(ip_address, domain))

  def remove_entry_by_domain(self, domain):
    self.find_entry(domain, None) 

  def toggle_entry_by_domain(self, domain):
    self.find_entry(domain, lambda entry, f: f.write("#" + entry) if not entry.startswith("#") else f.write(entry[1:]))

  def switch_profile(self, name, fresh=False):
    host_manager_profile_path = "{}/hosts.{}".format(self.base_dir, name)
    host_manager_original_path = "{}/{}".format(self.base_dir, self.HOST_MANAGER_DEFAULT_FILENAME)

    if not os.path.exists(host_manager_profile_path):
      if fresh:
        open(host_manager_profile_path, "w").close()
      else:
        copyfile(host_manager_original_path, host_manager_profile_path)

    if os.path.exists(self.HOST_FILE_PATH):
      os.unlink(self.HOST_FILE_PATH)
      os.symlink(host_manager_profile_path, self.HOST_FILE_PATH)

  def remove_profile(self, name):
    host_manager_profile_path = "{}/hosts.{}".format(self.base_dir, name)

    if os.path.exists(host_manager_profile_path):
      self.switch_profile("default")
      os.unlink(host_manager_profile_path)
  
  def find_entry(self, domain, callback):
    with open(self.HOST_FILE_PATH, "r+") as f:
      lines = f.readlines()
      f.seek(0)
      for line in lines:
        entry = re.split("\s", line)

        if entry[1] == domain or entry[1] == "#{}".format(domain):
          if callback: callback(line, f)
        else:
          f.write(line)

      f.truncate()

class HostShell(cmd.Cmd):
  intro = "Welcome to the Hosts editor shell. Type help or ? to list commands.\n"
  prompt = "hosts> "
  file = None
  hostFileManager = None
  profiles = []

  def __init__(self, hostFileManager):
    cmd.Cmd.__init__(self)
    self.hostFileManager = hostFileManager
    self.profiles = hostFileManager.get_profiles()

    self.set_prompt_name(self.hostFileManager.get_active_profile())

  def do_remove(self, domain):
    """remove <domain> - remove an entry to active profile"""
    self.hostFileManager.remove_entry_by_domain(domain)

  def complete_remove(self, text, line, begidx, endidx):
    return [domain.domain for domain in self.hostFileManager.get_entries(search=text)]

  def do_create(self, args):
    """create <domain> <ip address> - create an entry on active profile"""
    args = args.split()
    if len(args) != 2:
      self.onecmd("help add")

    self.hostFileManager.create_entry(args[0], args[1])

  def do_update(self, args):
    """update <domain> <ip address> - update an existing entry in active profile"""
    args = args.split()
    if len(args) != 2:
      self.onecmd("help replace")

    self.hostFileManager.remove_entry_by_domain(args[0])
    self.hostFileManager.create_entry(args[0], args[1])

  def do_toggle(self, domain):
    """toggle <domain> - toggle enabled status in hosts file"""
    self.hostFileManager.toggle_entry_by_domain(domain)

  def complete_toggle(self, text, line, begidx, endidx):
    return [domain.domain for domain in self.hostFileManager.get_entries(search=text)]

  def do_show(self, type):
    """show profiles|hosts - Display either the present profiles or the lists of hosts in a given profile"""

    if type == "profiles":
      for profile in self.hostFileManager.get_profiles():
        print "* {}".format(profile)
    elif type == "hosts":
      for host in self.hostFileManager.get_entries():
        print "[{}] {} => {}".format( "ACTIVE" if host.active else "INACTIVE", host.domain, host.ipaddr)

  def complete_show(self, text, line, begidx, endidx):
    show_types = ["profiles", "hosts"]
    show = [type for type in show_types if type.startswith(text)]

    if not show:
      show = show_types

    return show

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

    profiles = [profile for profile in profile_entries if profile.startswith(text)]

    if not profiles:
      profiles = profile_entries

    return profiles

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
    has_arg_set = [key for key in args.__dict__ if args.__dict__[key] is not None]

    if not has_arg_set:
      parser.print_help()
      sys.exit(0)

    hostFileManager = HostFileManager("/etc/hosts-editor")
    hostShell = HostShell(hostFileManager)

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