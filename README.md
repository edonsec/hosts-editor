## Hosts File Editor

Hosts editor is a standalone script for the sole purpose of managing your /etc/hosts file, it allows for multiple profiles and the toggling the active status for a given entry.

### Installation

Prerequisites:
* Python 2.7+
* Linux/Mac

The script can be installed in any location, it must be run as root in order to safely edit the /etc/hosts file.

A recommended location would be '/usr/sbin/hosts' for ease of access.

### Usage

There are two operating modes for the script, one is command line through the use of arguments, the other is an interactive mode.

#### Interactive mode

There is full support for tab completion providing your terminal supports readline. Hit <TAB><TAB> to auto complete commands.

Example interactive session:

```
Welcome to the Hosts editor shell. Type help or ? to list commands.

hosts/default> show hosts
[ACTIVE] localhost => 127.0.0.1
[ACTIVE] broadcasthost => 255.255.255.255
[ACTIVE] localhost => ::1
[ACTIVE] mydomain.com => 128.0.1.1
hosts/default> show profiles
* default
* production
* staging
hosts/default> profile production
hosts/production> show hosts
[ACTIVE] localhost => 127.0.0.1
[ACTIVE] broadcasthost => 255.255.255.255
[ACTIVE] localhost => ::1
[ACTIVE] mydomain.com => 127.0.0.1
hosts/production> update mydomain.com 1.2.3.4
hosts/production> show hosts
[ACTIVE] localhost => 127.0.0.1
[ACTIVE] broadcasthost => 255.255.255.255
[ACTIVE] localhost => ::1
[ACTIVE] mydomain.com => 1.2.3.4
hosts/production> toggle mydomain.com
hosts/production> show hosts
[ACTIVE] localhost => 127.0.0.1
[ACTIVE] broadcasthost => 255.255.255.255
[ACTIVE] localhost => ::1
[INACTIVE] mydomain.com => 1.2.3.4
hosts/default> create new.mydomain.com 4.5.6.7
hosts/default> show hosts
[ACTIVE] localhost => 127.0.0.1
[ACTIVE] broadcasthost => 255.255.255.255
[ACTIVE] localhost => ::1
[ACTIVE] mydomain.com => 128.0.1.1
[ACTIVE] new.mydomain.com => 4.5.6.7
```

#### Command line mode

```
usage: hosts.py [-h] [--profile PROFILE] [--create DOMAIN IP_ADDRESS]
                [--remove DOMAIN] [--update DOMAIN IP_ADDRESS]
                [--toggle DOMAIN] [--show {hosts,profiles}] [--interactive]

optional arguments:
  -h, --help            show this help message and exit
  --profile PROFILE, -p PROFILE
                        Specify profile
  --create DOMAIN IP_ADDRESS, -c DOMAIN IP_ADDRESS
                        Create host entry; Args: <domain> <ip address>
  --remove DOMAIN, -r DOMAIN
                        Remove host entry by domain
  --update DOMAIN IP_ADDRESS, -u DOMAIN IP_ADDRESS
                        Update existing host entry
  --toggle DOMAIN, -t DOMAIN
                        Toggle host entry by domain
  --show {hosts,profiles}, -s {hosts,profiles}
                        Show hosts or profiles
  --interactive, -i     Interactive mode

$ sudo ./hosts.py --create foo.com 1.2.3.4
$ sudo ./hosts.py --update bar.com 4.5.6.7
$ sudo ./hosts.py --show profiles
* default
* production
* staging
```

## File structure

On launch the following file structure is created:

 - /etc/hosts-editor
    - hosts.default
 - /etc/hosts.original
 - /etc/hosts -> /etc/hosts-editor/hosts.default (symlink)

All future profiles are stored within /etc/hosts-editor and can be manually updated at any time if necessary. A backup of your original /etc/hosts is kept in /etc/hosts.original and is there if normal functionality needs to be restored.
