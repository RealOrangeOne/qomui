import json
import shlex
import os
import logging
from subprocess import check_call, check_output, CalledProcessError, Popen, PIPE, STDOUT
from PyQt5 import QtCore, QtGui, Qt, QtWidgets
from collections import Counter

ROOTDIR = "/usr/share/qomui"
saved_rules = []
saved_rules_6 = []
ip_cmd = ["iptables", "--wait",]
ip6_cmd = ["ip6tables", "--wait",]
devnull = open(os.devnull, 'w')

def add_rule(rule):
    a = 1
    try:
        check = rule[:]
        if "-D" not in check:
            if check[0] == "-A":
                check[0] = "-C"
            elif check[0] == "-I":
                check[0] = "-C"
                check.pop(2)
            elif check[2] == "-A":
                check[2] = "-C"
            check_call(ip_cmd + check, stdout=devnull, stderr=devnull)
            logging.debug("iptables: {} already exists".format(rule))
            a = 0
    except (IndexError, CalledProcessError):
        pass

    try:
        if a == 1:
            check_call(ip_cmd + rule, stdout=devnull, stderr=devnull)
            logging.debug("iptables: applied {}".format(rule))

    except CalledProcessError:
        if "-D" not in rule:
            logging.warning("iptables: failed to apply {}".format(rule))

def add_rule_6(rule):
    a = 1
    try:
        check = rule[:]
        if "-D" not in check:
            if check[0] == "-A":
                check[0] = "-C"
            elif check[0] == "-I":
                check[0] = "-C"
                check.pop(2)
            elif check[2] == "-A":
                check[2] = "-C"
            check_call(ip6_cmd + check, stdout=devnull, stderr=devnull)
            logging.debug("ipt6ables: {} already exists".format(rule))
            a = 0
    except (IndexError, CalledProcessError):
        pass

    try:
        if a == 1:
            check_call(ip6_cmd + rule, stdout=devnull, stderr=devnull)
            logging.debug("ip6tables: applied {}".format(rule))

    except CalledProcessError:
        if "-D" not in rule:
            logging.warning("ip6tables: failed to apply {}".format(rule))

def apply_rules(opt, block_lan=0, preserve=0):
    fw_rules = get_config()
    save_existing_rules(fw_rules)
    save_existing_rules_6(fw_rules)

    for rule in fw_rules["flush"]:
        add_rule(rule)

    for rule in fw_rules["flushv6"]:
        add_rule_6(rule)

    logging.info("iptables: flushed existing rules")

    for rule in saved_rules:
        if preserve == 1:
            add_rule(rule)

    for rule in saved_rules_6:
        if preserve == 1:
            add_rule_6(rule)

    if opt == 1:
        for rule in fw_rules["defaults"]:
            add_rule(rule)

        if block_lan == 0:
            for rule in fw_rules["ipv4local"]:
                add_rule(rule)

            for rule in fw_rules["ipv6local"]:
                add_rule_6(rule)

        for rule in fw_rules["defaultsv6"]:
            add_rule_6(rule)

        for rule in fw_rules["ipv4rules"]:
            add_rule(rule)

        for rule in fw_rules["ipv6rules"]:
            add_rule_6(rule)

        logging.info("iptables: activated firewall")

    elif opt == 0:
        for rule in fw_rules["unsecure"]:
            add_rule(rule)

        for rule in fw_rules["unsecurev6"]:
            add_rule_6(rule)

        logging.info("iptables: deactivated firewall")

def save_existing_rules(fw_rules):
    existing_rules = check_output(["iptables", "-S"]).decode("utf-8")
    for line in existing_rules.split('\n'):
        rpl = line.replace("/32", "")
        rule = shlex.split(rpl)
        if len(rule) != 0:
            match = 0
            omit = fw_rules["ipv4rules"] + fw_rules["flush"] + fw_rules["ipv4local"]
            for x in omit:
                if Counter(x) == Counter(rule):
                    match = 1
            if match == 0 and rule not in saved_rules:
                saved_rules.append(rule)
            match = 0

def save_existing_rules_6(fw_rules):
    existing_rules = check_output(["ip6tables", "-S"]).decode("utf-8")
    for line in existing_rules.split('\n'):
        rpl = line.replace("/32", "")
        rule = shlex.split(rpl)
        if len(rule) != 0:
            match = 0
            omit = fw_rules["ipv6rules"] + fw_rules["flushv6"] + fw_rules["ipv6local"]
            for x in omit:
                if Counter(x) == Counter(rule):
                    match = 1
            if match == 0 and rule not in saved_rules_6:
                saved_rules_6.append(rule)
            match = 0

def allow_dest_ip(ip, action):
    rule = [action, 'OUTPUT', '-d', ip, '-j', 'ACCEPT']

    try:
        if len(ip.split(".")) == 4:
            add_rule(rule)

        elif len(ip.split(":")) >= 4:
            add_rule_6(rule)
    except:
        pass

def get_config():
    try:
        with open("{}/firewall.json".format(ROOTDIR), "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
        logging.debug("Loading default firewall configuration")
        try:
            with open("{}/firewall_default.json".format(ROOTDIR), "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError) as e:
            logging.debug("Failed to load firewall configuration")
            return None

def check_firewall_services():
    firewall_services = ["ufw", "firewalld"]
    detected_firewall = []

    for fw in firewall_services:

        try:
            result = check_output(["systemctl", "is-enabled", fw], stderr=devnull).decode("utf-8")

            if result == "enabled\n":
                detected_firewall.append(fw)
                logging.warning("Detected enable firewall service: {}".format(fw))

            else:
                logging.debug("{}.service is not enabled".format(fw))

        except (FileNotFoundError, CalledProcessError) as e:
            logging.debug("{}.service does either not exist or is not enabled".format(fw))

    return detected_firewall

def save_iptables():
    outfile = open("{}/iptables_before.rules".format(ROOTDIR), "w")
    save = Popen(["iptables-save"], stdout=outfile, stderr=PIPE)
    save.wait()
    outfile.flush()

    if save.stderr:
        logging.debug("Failed to save current iptables rules")

    else:
        logging.debug("Saved iptables rule")

def restore_iptables():
    infile = open("{}/iptables_before.rules".format(ROOTDIR), "r")
    restore = Popen(["iptables-restore"], stdin=infile, stderr=PIPE)
    save.wait()

    if restore.stderr:
        logging.debug("Failed to restore iptables rules")

    else:
        logging.debug("restored previous iptables rules")




