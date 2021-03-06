#!/usr/bin/env python3
"DN42 Schema Checker"

from __future__ import print_function

import re
import os
import sys
import time
import argparse
import glob
import urllib.parse
import http.client
import json

import log

SCHEMA_NAMESPACE = "dn42."


class SchemaDOM:
    "schema"
    def __init__(self, fn):
        self.name = None
        self.ref = None
        self.primary = None
        self.type = None
        self.src = fn
        f = FileDOM(fn)
        self.schema = self.__parse_schema(f)

    def __parse_schema(self, f):
        schema = {}
        for key, val, _ in f.dom:
            if key == "ref":
                self.ref = val
            elif key == "schema":
                self.name = val

            if key != "key":
                continue

            val = val.split()
            key = val.pop(0)

            schema[key] = set()
            for i in val:
                if i == ">":
                    break

                schema[key].add(i)

            for k, v in schema.items():
                if "schema" in v:
                    self.type = k

                if "primary" in v:
                    self.primary = k
                    schema[k].add("oneline")
                    if "multiline" in v:
                        schema[k].remove("multiline")
                    schema[k].add("single")
                    if "multiple" in v:
                        schema[k].remove("multiple")
                    schema[k].add("required")
                    if "optional" in v:
                        schema[k].remove("optional")
                    if "recommend" in v:
                        schema[k].remove("recommend")
                    if "deprecate" in v:
                        schema[k].remove("deprecate")

                if "oneline" not in v:
                    schema[k].add("multiline")
                if "single" not in v:
                    schema[k].add("multiple")

        return schema

    def check_file(self, f, lookups=None):
        "check file"
        status = "PASS"
        if not f.valid:
            log.error("%s Line 0: File does not parse" % (f.src))
            status = "FAIL"

        for k, v in self.schema.items():
            if "required" in v and k not in f.keys:
                log.error("%s Line 0: Key [%s] not found and is required." % (f.src, k))
                status = "FAIL"
            elif "recommend" in v and k not in f.keys:
                log.notice(
                    "%s Line 0: Key [%s] not found and is recommended." % (f.src, k)
                )
                status = "NOTE"

            if "schema" in v and SCHEMA_NAMESPACE + f.dom[0][0] != self.ref:
                log.error(
                    "%s Line 1: Key [%s] not found and is required as the first line."
                    % (f.src, k)
                )
                status = "FAIL"

            if "single" in v and k in f.keys and len(f.keys[k]) > 1:
                log.warning(
                    "%s Line %d: Key [%s] first defined here and has repeated keys."
                    % (f.src, f.keys[k][0], k)
                )
                for l in f.keys[k][1:]:
                    log.error(
                        "%s Line %d: Key [%s] can only appear once." % (f.src, l, k)
                    )
                    status = "FAIL"

            if "oneline" in v and k in f.multi:
                for l in f.keys[k]:
                    log.error(
                        "%s Line %d: Key [%s] can not have multiple lines."
                        % (f.src, l, k)
                    )
                    status = "FAIL"

        for k, v, l in f.dom:
            if k == self.primary and not f.src.endswith(
                    v.replace("/", "_").replace(" ", "")):
                log.error(
                    "%s Line %d: Primary [%s: %s] does not match filename."
                    % (f.src, l, k, v)
                )
                status = "FAIL"

            if k.startswith("x-"):
                log.info("%s Line %d: Key [%s] is user defined." % (f.src, l, k))

            elif k not in self.schema:
                log.error("%s Line %d: Key [%s] not in schema." % (f.src, l, k))
                status = "FAIL"
                continue
            else:
                if "deprecate" in self.schema[k]:
                    log.info(
                        "%s Line %d: Key [%s] was found and is deprecated."
                        % (f.src, l, k)
                    )
                    status = "INFO"

                if lookups is not None:
                    for o in self.schema[k]:
                        if o.startswith("lookup="):
                            refs = o.split("=", 2)[1].split(",")
                            val = v.split()[0]
                            found = False
                            for ref in refs:
                                if (ref, val) in lookups:
                                    found = True
                            if not found:
                                log.error(
                                    "%s Line %d: Key %s references object %s in %s but does not exist."
                                    % (f.src, l, k, val, refs)
                                )
                                status = "FAIL"
        if status != "FAIL":
            ck = sanity_check(f)
            if ck == "FAIL":
                status = ck

        print("CHECK\t%-54s\t%s\tMNTNERS: %s" % (f.src, status, ",".join(f.mntner)))
        return status


class FileDOM:
    "file"
    def __init__(self, fn):
        self.valid = True
        self.dom = []
        self.keys = {}
        self.multi = {}
        self.mntner = []
        self.schema = None
        self.src = fn

        with open(fn, mode="r", encoding="utf-8") as f:
            dom = []
            keys = {}
            multi = {}
            mntner = []
            last_multi = None

            for lineno, i in enumerate(f.readlines(), 1):
                if re.match(r"[ \t]", i):
                    if len(dom) == 0:
                        log.error("File %s does not parse properly" % (fn))
                        self.valid = False
                        return

                    dom[-1][1] += "\n" + i.strip()

                    if dom[-1][0] not in multi:
                        multi[dom[-1][0]] = []

                    if last_multi is None:
                        multi[dom[-1][0]].append(lineno)
                        last_multi = dom[-1][0]

                else:
                    i = i.split(":")
                    if len(i) < 2:
                        continue

                    dom.append([i[0].strip(), ":".join(i[1:]).strip(), lineno - 1])

                    if i[0].strip() not in keys:
                        keys[i[0].strip()] = []

                    keys[i[0].strip()].append(len(dom) - 1)

                    last_multi = None

                if dom[-1][0] == "mnt-by":
                    mntner.append(dom[-1][1])

        self.dom = dom
        self.keys = keys
        self.multi = multi
        self.mntner = mntner
        self.schema = SCHEMA_NAMESPACE + dom[0][0]

    def __str__(self):
        length = 19
        for i in self.dom:
            if len(i[0]) > length:
                length = len(i[0]) + 2
        s = ""
        for i in self.dom:
            l = i[1].split("\n")

            s += i[0] + ":" + " " * (length - len(i[0])) + l[0] + "\n"
            for m in l[1:]:
                s += " " * (length + 1) + m + "\n"

        return s

    def get(self, key, index=0, default=None):
        "get value"
        if key not in self.keys:
            return default
        if index >= len(self.keys[key]) or index <= -len(self.keys[key]):
            return default

        return self.dom[self.keys[key][index]][1]


def main(infile, schema):
    "main command"
    log.debug("Check File: %s" % (infile))
    f = FileDOM(infile)

    if schema is not None:
        f.schema = schema
    else:
        f.schema = "schema/" + f.schema

    if f.schema is None:
        log.error("Schema is not defined for file")
        return False

    log.debug("Use Schema: %s" % (f.schema))

    s = SchemaDOM(f.schema)
    return s.check_file(f)


def check_schemas(path):
    "check schemas"
    schemas = {}
    for fn in glob.glob(path + "/*"):
        s = SchemaDOM(fn)
        log.info("read schema: %s" % (s.name))
        schemas[s.ref] = s

    ok = True
    c = schemas[SCHEMA_NAMESPACE + "schema"]
    for s in schemas:
        ck = c.check_file(s)
        if not ck:
            ok = False

    return ok


def scan_index(infile, mntner=None):
    "scan index"
    idx = {}
    schemas = {}

    with open(infile, "r") as f:
        for line in f.readlines():
            line = line.split()
            idx[(line[0], line[1])] = line[2:]
            if line[0] == SCHEMA_NAMESPACE + "schema":
                s = SchemaDOM(line[2])
                log.info("read schema: %s" % (s.name))
                schemas[s.ref] = s

    return __scan_index(idx, schemas, mntner)


def scan_files(path, mntner=None, use_file=None):
    "scan files"
    arr = __index_files(path, use_file)

    idx = {}
    schemas = {}

    for dom in arr:
        line = (
            dom.schema,
            dom.src.split("/")[-1].replace("_", "/"),
            dom.src,
            ",".join(dom.mntner),
            dom,
        )

        idx[(line[0], line[1])] = line[2:]
        if line[0] == SCHEMA_NAMESPACE + "schema":
            s = SchemaDOM(line[2])
            schemas[s.ref] = s

    return __scan_index(idx, schemas, mntner, use_file)


def __scan_index(idx, schemas, mntner, use_file=None):
    ok = True
    for k, v in idx.items():
        if use_file is not None and use_file != v[0]:
            continue

        s = schemas.get(k[0], None)
        if s is None:
            log.error("No schema found for %s" % (k[1]))
            print("CHECK\t%-54s\tFAIL\tMNTNERS: UNKNOWN" % (v[2].src))
            ok = "FAIL"

        else:
            mlist = []
            if len(v) > 1:
                mlist = v[1].split(",")

            if mntner is not None and mntner not in mlist:
                continue

            c = v[2]
            ck = s.check_file(c, idx.keys())

            if ck == "INFO" and ok != "FAIL":
                ok = ck
            if ck == "FAIL":
                ok = ck
    return ok


def __index_files(path, use_file=None):
    xlat = {
        "dns/": SCHEMA_NAMESPACE + "domain",
        "inetnum/": SCHEMA_NAMESPACE + "inetnum",
        "inet6num/": SCHEMA_NAMESPACE + "inet6num",
        "route/": SCHEMA_NAMESPACE + "route",
        "route6/": SCHEMA_NAMESPACE + "route6",
        "aut-num/": SCHEMA_NAMESPACE + "aut-num",
        "as-set/": SCHEMA_NAMESPACE + "as-set",
        "as-block/": SCHEMA_NAMESPACE + "as-block",
        "organisation/": SCHEMA_NAMESPACE + "organisation",
        "mntner/": SCHEMA_NAMESPACE + "mntner",
        "person/": SCHEMA_NAMESPACE + "person",
        "role/": SCHEMA_NAMESPACE + "role",
        "tinc-key/": SCHEMA_NAMESPACE + "tinc-key",
        "tinc-keyset/": SCHEMA_NAMESPACE + "tinc-keyset",
        "registry/": SCHEMA_NAMESPACE + "registry",
        "schema/": SCHEMA_NAMESPACE + "schema",
    }

    for root, _, files in os.walk(path):
        ignore = True
        for t in xlat:
            if root + "/" == os.path.join(path, t):
                ignore = False
                break
        if ignore:
            continue

        for f in files:
            if f[0] == ".":
                continue
            dom = FileDOM(os.path.join(root, f))
            yield dom

    if use_file is not None:
        dom = FileDOM(use_file)
        yield dom


def index_files(path):
    "index files"
    idx = __index_files(path)
    for i in idx:
        print("%s\t%s\t%s\t%s" % i)


def http_get(server, url, query=None, headers=None):
    "http get"
    if headers is None:
        headers = {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "curl"
    if "Accept" not in headers:
        headers["Accept"] = "application/json"

    if query is None:
        query = {}

    http_client = http.client.HTTPSConnection(server)

    full_url = url + "?" + urllib.parse.urlencode(query)
    log.debug("GET " + full_url)

    http_client.request("GET", full_url, headers=headers)
    req = http_client.getresponse()
    log.debug("HTTP Response: %d %s" % (req.status, req.reason))

    if "application/json" in req.getheader("Content-Type", "application/json"):
        if req.status > 299:
            return {}
        r = req.read()
        if not isinstance(r, str):
            r = r.decode("utf-8")
        return json.loads(r)

    if req.status > 299:
        return ""

    return req.read()


def find(fields=None, filters=None):
    "find"
    server = "registry.dn42.us"
    url = "/v1/reg/reg.objects"
    if fields is None:
        fields = []
    if filters is None:
        filters = {}
    query = {
        "fields": ",".join(fields),
        "filter": ",".join([k + "=" + v for k, v in filters.items()]),
    }
    return http_get(server, url, query)


def to_num(ip):
    "ip to number"
    ip = [int(i) for i in ip.split(".")]
    return ip[3] + ip[2] * 256 + ip[1] * 256 ** 2 + ip[0] * 256 ** 3


def to_ip(num):
    "number to ip"
    return ".".join(
        [str(i) for i in [num >> 24, (num >> 16) & 0xFF, (num >> 8) & 0xFF, num & 0xFF]]
    )


def pretty_ip(addr):
    "pretty ip"
    if addr.startswith("00000000000000000000ffff"):
        addr = addr[-8:]
        addr = int(addr, 16)
        return to_ip(addr)
    return ":".join([addr[i:i + 4] for i in range(0, len(addr), 4)])


def expand_ipv6(addr):
    "expand ip6"
    addr = addr.lower()
    if "::" in addr:
        if addr.count("::") > 1:
            return False
        addr = addr.replace("::", ":" * (9 - addr.count(":")))
    if addr.count(":") != 7:
        return False
    return "".join((i.zfill(4) for i in addr.split(":")))


def ip4_to_ip6(ip):
    "ip4 to ip6"
    return "::ffff:%04x:%04x" % (ip >> 16, ip & 0xFFFF)


def inetrange(inet):
    "inet range"
    ip, mask = inet.split("/")
    mask = int(mask)
    ip = to_num(ip) & (0xFFFFFFFF << 32 - mask)
    ip6 = ip4_to_ip6(ip)
    return inet6range("%s/%d" % (ip6, mask + 96))


def inet6range(inet):
    "inet6 range"
    ip, mask = inet.split("/")
    mask = int(mask)

    log.debug(ip)
    ip = expand_ipv6(ip)

    if mask == 128:
        return ip, ip, mask

    offset = int(ip[mask // 4], 16)
    return (
        "%s%x%s"
        % (ip[: mask // 4], offset & (0xF0 >> mask % 4), "0" * (31 - mask // 4)),
        "%s%x%s"
        % (ip[: mask // 4], offset | (0xF >> mask % 4), "f" * (31 - mask // 4)),
        mask,
    )


def test_policy(obj_type, name, mntner):
    "test policy"
    log.debug([obj_type, name, mntner])

    if obj_type in ["organisation",
                    "mntner",
                    "person",
                    "role",
                    "as-set",
                    "schema",
                    "dns",
                    ]:
        if obj_type == "organisation" and not name.startswith("ORG-"):
            log.error("%s does not start with 'ORG-'" % (name))
            return "FAIL"
        elif obj_type == "mntner" and not name.endswith("-MNT"):
            log.error("%s does not end with '-MNT'" % (name))
            return "FAIL"
        elif obj_type == "dns" and not name.endswith(".dn42"):
            log.error("%s does not end with '.dn42'" % (name))
            return "FAIL"
        elif obj_type == "dns" and len(name.strip(".").split(".")) != 2:
            log.error("%s is not a second level domain" % (name))
            return "FAIL"
        elif obj_type in ["person", "role"] and not name.endswith("-DN42"):
            log.error("%s does not end with '-DN42'" % (name))
            return "FAIL"

        lis = find(["mnt-by"], {"@type": obj_type, "@name": name})
        log.debug(lis)

        if len(lis) == 0:
            log.notice("%s does not currently exist" % (name))
            return "PASS"

        status = "FAIL"
        for o in lis:
            for n in o:
                log.debug(n)
                log.debug(mntner)
                if n[0] == "mnt-by" and n[1] == mntner:
                    status = "PASS"
                    return status

        log.error("%s does not have mnt for object" % (mntner))
        return status

    elif obj_type in ["inetnum", "inet6num"]:
        log.info("Checking inetnum type")
        lis = find(["mnt-by"], {"@type": "net", "cidr": name})
        log.debug(lis)

        if len(lis) > 0:
            status = "FAIL"
            for o in lis:
                for n in o:
                    if n[0] == "mnt-by" and n[1] == mntner:
                        status = "PASS"
                        log.notice("%s has mnt for current object" % (mntner))
                        return status
            log.error("%s does not have mnt for current object" % (mntner))
            return status

        if obj_type == "inetnum":
            Lnet, Hnet, mask = inetrange(name)
        else:
            Lnet, Hnet, mask = inet6range(name)

        mask = "%03d" % (mask)

        log.info([Lnet, Hnet, mask])
        lis = find(
            ["inetnum", "inet6num", "policy", "@netlevel", "mnt-by", "mnt-lower"],
            {
                "@type": "net",
                "@netmin": "le=" + Lnet,
                "@netmax": "ge=" + Hnet,
                "@netmask": "lt=" + mask,
            },
        )
        log.debug(lis)

        policy = {}
        select = None
        mntners = []

        for n in lis:
            obj = {}
            for o in n:
                obj[o[0]] = o[1]
                if o[0].startswith("mnt-"):
                    mntners.append(o[1])

            k = obj["@netlevel"]
            policy[k] = obj

            if select is None:
                select = k
            elif select <= k:
                select = k

        if select is None:
            pass

        elif policy.get(select, {}).get("policy", "closed") == "open":
            log.notice("Policy is open for parent object")
            return "PASS"

        # 3. Check if mntner or mnt-lower for any as-block in the tree.
        elif mntner in mntners:
            log.notice("%s has mnt in parent object" % (mntner))
            return "PASS"

    elif obj_type in ["route", "route6"]:
        log.info("Checking route type")
        lis = find(["mnt-by"], {"@type": "route", obj_type: name})
        log.debug(lis)

        if len(lis) > 0:
            status = "FAIL"
            for o in lis:
                for n in o:
                    if n[0] == "mnt-by" and n[1] == mntner:
                        status = "PASS"
                        log.notice("%s has mnt for current object" % (mntner))
                        return status
            log.error("%s does not have mnt for current object" % (mntner))
            return status

        if obj_type == "route":
            Lnet, Hnet, mask = inetrange(name)
        else:
            Lnet, Hnet, mask = inet6range(name)
        mask = "%03d" % (mask)

        log.info([Lnet, Hnet, mask])
        lis = find(
            ["inetnum", "inet6num", "policy", "@netlevel", "mnt-by", "mnt-lower"],
            {
                "@type": "net",
                "@netmin": "le=" + Lnet,
                "@netmax": "ge=" + Hnet,
                "@netmask": "le=" + mask,
            },
        )
        log.debug(lis)

        policy = {}
        select = None
        mntners = []

        for n in lis:
            obj = {}
            for o in n:
                obj[o[0]] = o[1]
                if o[0].startswith("mnt-"):
                    mntners.append(o[1])

            k = obj["@netlevel"]
            policy[k] = obj

            if select is None:
                select = k
            elif select <= k:
                select = k

        if select is None:
            pass

        elif policy.get(select, {}).get("policy", "closed") == "open":
            log.notice("Policy is open for parent object")
            return "PASS"

        # 3. Check if mntner or mnt-lower for any as-block in the tree.
        elif mntner in mntners:
            log.notice("%s has mnt in parent object" % (mntner))
            return "PASS"

    elif obj_type == "aut-num":
        if not name.startswith("AS"):
            log.error("%s does not start with AS" % (name))
            return "FAIL"

        # 1. Check if they already have an object
        lis = find(["mnt-by"], {"@type": "aut-num", "@name": name})
        log.debug(lis)

        if len(lis) > 0:
            status = "FAIL"
            for o in lis:
                for n in o:
                    if n[0] == "mnt-by" and n[1] == mntner:
                        status = "PASS"
                        log.notice("%s has mnt for current object" % (mntner))
                        return status
            log.error("%s does not have mnt for current object" % (mntner))
            return status

        # 2. Check if the as-block has an open policy
        asn = "AS{:0>9}".format(name[2:])
        lis = find(
            ["as-block", "policy", "@as-min", "@as-max", "mnt-by", "mnt-lower"],
            {"@type": "as-block", "@as-min": "le=" + asn, "@as-max": "ge=" + asn},
        )
        log.info(lis)

        policy = {}
        select = None
        mntners = []

        for n in lis:
            obj = {}
            for o in n:
                obj[o[0]] = o[1]
                if o[0].startswith("mnt-"):
                    mntners.append(o[1])

            k = (obj["@as-min"], obj["@as-max"])
            policy[k] = obj

            if select is None:
                select = k
            elif select[0] <= k[0] or select[1] >= k[1]:
                select = k

        if policy.get(select, {}).get("policy", "closed") == "open":
            log.notice("Policy is open for parent object")
            return "PASS"

        # 3. Check if mntner or mnt-lower for any as-block in the tree.
        elif mntner in mntners:
            log.notice("%s has mnt in parent object" % (mntner))
            return "PASS"

    elif obj_type == "as-block":
        Lname, Hname = name.split("-")
        Lname, Hname = Lname.strip(), Hname.strip()

        if not Lname.startswith("AS") or not Hname.startswith("AS"):
            log.error("%s does not start with AS for min and max" % (name))
            return "FAIL"

        # 1. Check if they already have an object
        lis = find(["mnt-by"], {"@type": "as-block", "@name": name})
        log.debug(lis)

        if len(lis) > 0:
            status = "FAIL"
            for o in lis:
                for n in o:
                    if n[0] == "mnt-by" and n[1] == mntner:
                        status = "PASS"
                        log.notice("%s has mnt for current object" % (mntner))
                        return status
            log.notice("%s does not have mnt for current object" % (mntner))
            return status

        # 2. Check if the parent as-blocks have an open policy
        Lasn = "AS{:0>9}".format(Lname[2:])
        Hasn = "AS{:0>9}".format(Hname[2:])

        if Lasn > Hasn:
            log.error("%s should come before %s" % (Lname, Hname))

        lis = find(
            ["as-block", "policy", "@as-min", "@as-max", "mnt-by", "mnt-lower"],
            {"@type": "as-block", "@as-min": "le=" + Lasn, "@as-max": "ge=" + Hasn},
        )
        log.debug(lis)

        policy = {}
        select = None
        mntners = []

        for n in lis:
            obj = {}
            for o in n:
                obj[o[0]] = o[1]
                if o[0].startswith("mnt-"):
                    mntners.append(o[1])

            k = (obj["@as-min"], obj["@as-max"])
            policy[k] = obj

            if select is None:
                select = k
            elif select[0] <= k[0] or select[1] >= k[1]:
                select = k

        # Policy Open only applies to aut-nums. as-blocks must be defined by parent mntners only.
        #
        #   if policy[select]["policy"] == "open":
        #       log.notice("Policy is open for parent object")
        #       return "PASS"

        # 3. Check if mntner or mnt-lower for any as-block in the tree.
        if mntner in mntners:
            log.notice("%s has mnt in parent object" % (mntner))
            return "PASS"

    log.error("%s does not pass checks for %s %s" % (mntner, obj_type, name))
    return "FAIL"


def sanity_check(dom):
    "sanity check"
    ck = "PASS"
    if dom.schema == "dn42.inetnum":
        cidr = dom.get("cidr")
        Lnet, Hnet, _ = inetrange(cidr)
        cidr_range = pretty_ip(Lnet) + "-" + pretty_ip(Hnet)
        file_range = dom.get("inetnum")
        file_range = re.sub(r"\s+", "", file_range, flags=re.UNICODE)

        if cidr_range != file_range:
            log.error(
                "inetnum range [%s] does not match: [%s]" % (file_range, cidr_range)
            )
            ck = "FAIL"

    if dom.schema == "dn42.inet6num":
        cidr = dom.get("cidr")
        log.info(cidr)
        Lnet, Hnet, _ = inet6range(cidr)
        cidr_range = pretty_ip(Lnet) + "-" + pretty_ip(Hnet)
        file_range = dom.get("inet6num")
        file_range = re.sub(r"\s+", "", file_range, flags=re.UNICODE)

        if cidr_range != file_range:
            log.error(
                "inetnum range [%s] does not match: [%s]" % (file_range, cidr_range)
            )
            ck = "FAIL"

    return ck


def get_args():
    """Get and parse command line arguments"""

    parser = argparse.ArgumentParser(
        description="Check Schema. Checks Schema of file for validity"
    )
    parser.add_argument(
        "--merge-output",
        help="Merge stderr into stdout (helps when reading output with pagers) [Default OFF]",
        action="store_true",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Enable verbose output [Default OFF]",
        action="store_true",
    )
    parser.add_argument(
        "-vv",
        "--doubleVerbose",
        help="Enable full verbose output [Default OFF]",
        action="store_true",
    )

    subparsers = parser.add_subparsers(help="sub-command help", dest="command")

    parser_file = subparsers.add_parser("check-file", help="Process a specific file")
    parser_file.add_argument(
        "-s",
        "--use-schema",
        nargs="?",
        help="Override schema to validate [Default None]",
        action="store",
    )
    parser_file.add_argument("infile", nargs="?", help="File to check", type=str)

    parser_schema = subparsers.add_parser("check-schemas", help="Validate all schemas")
    parser_schema.add_argument("path", nargs="?", help="Path for schemas", type=str)

    parser_index = subparsers.add_parser("index", help="Generate index")
    parser_index.add_argument("path", nargs="?", help="Path for dn42 data", type=str)

    parser_scanindex = subparsers.add_parser(
        "scan-index", help="Validate files in index"
    )
    parser_scanindex.add_argument(
        "infile", nargs="?", help="Index file to scan", type=str
    )
    parser_scanindex.add_argument(
        "-m",
        "--use-mntner",
        nargs="?",
        help="Only scan files that has MNT [Default None]",
        action="store",
    )

    parser_scan = subparsers.add_parser("scan", help="Validate files in index")
    parser_scan.add_argument("path", nargs="?", help="Path for dn42 data", type=str)
    parser_scan.add_argument(
        "-m",
        "--use-mntner",
        nargs="?",
        help="Only scan files that has a matching MNT [Default None]",
        action="store",
    )
    parser_scan.add_argument(
        "-f",
        "--use-file",
        nargs="?",
        help="Only scan file given [Default None]",
        action="store",
    )

    parser_fmt = subparsers.add_parser("fmt", help="Format file")
    parser_fmt.add_argument(
        "infile", nargs="?", help="Path for dn42 data file", type=str
    )
    parser_fmt.add_argument(
        "-i", "--in-place", help="Format file in place", action="store_true"
    )

    parser_sane = subparsers.add_parser(
        "sanity-check", help="Check the file for sane-ness"
    )
    parser_sane.add_argument(
        "infile", nargs="?", help="Path for dn42 data file", type=str
    )

    parser_pol = subparsers.add_parser("policy", help="Format file")
    parser_pol.add_argument("type", nargs="?", type=str, help="dn42 object type")
    parser_pol.add_argument("name", nargs="?", type=str, help="dn42 object name")
    parser_pol.add_argument("mntner", nargs="?", type=str, help="dn42 object mntner")

    parser_mroute = subparsers.add_parser(
        "match-routes", help="Match routes to inetnums"
    )
    _ = parser_mroute

    return vars(parser.parse_args())


def run(args):
    "run"
    if args["merge_output"]:
        log.OUTPUT = sys.stdout

    if args["doubleVerbose"]:
        log.default.level_console = log.VERB_DEBUG
        log.default.level_full = True

    if args["verbose"]:
        log.default.level_console = log.VERB_INFO

    log.debug(args)

    valid = True
    if args["command"] == "check-file":
        valid = main(args["infile"], args["use_schema"])
        if valid:
            log.notice("Check %s: PASS" % (args["infile"]))
        else:
            log.fatal("Check %s: FAIL" % (args["infile"]))

    elif args["command"] == "check-schemas":
        valid = check_schemas(args["path"])

    elif args["command"] == "index":
        index_files(args["path"])

    elif args["command"] == "scan-index":
        scan_index(args["infile"], args["use_mntner"])

    elif args["command"] == "scan":
        log.notice(
            "## Scan Started at %s"
            % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )
        ck = scan_files(args["path"], args["use_mntner"], args["use_file"])
        log.notice(
            "## Scan Completed at %s"
            % (time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()))
        )

        if ck == "INFO":
            sys.exit(2)
        elif ck == "FAIL":
            sys.exit(1)

    elif args["command"] == "fmt":
        dom = FileDOM(args["infile"])
        if args["in_place"]:
            with open(args["infile"], "w+") as f:
                f.write(str(dom))
        else:
            print(str(dom))

    elif args["command"] == "policy":

        if args["type"] is None:
            log.fatal("Type should be provided")

        if args["name"] is None:
            log.fatal("Name should be provided")

        if args["mntner"] is None:
            log.fatal("Mntner should be provided")

        if args["type"] in ["inetnum", "inet6num", "route", "route6"]:
            args["name"] = args["name"].replace("_", "/")

        status = test_policy(args["type"], args["name"], args["mntner"])

        print(
            "POLICY %-12s\t%-8s\t%20s\t%s"
            % (args["mntner"], args["type"], args["name"], status)
        )
        if status != "PASS":
            sys.exit(1)

    elif args["command"] == "sanity-check":
        dom = FileDOM(args["infile"])
        ck = sanity_check(dom)
        print("SANITY %-8s\t%20s\t%s" % (dom.schema.split(".")[1], args["infile"], ck))
        if ck != "PASS":
            sys.exit(1)

    elif args["command"] == "match-routes":
        lis = find(
            ["mnt-by", "cidr", "route", "@netlevel", "@netmin", "@netmax", "@uri"],
            {"@family": "ipv4"},
        )

        def field(x, field):
            for i in x:
                if i[0] == field:
                    return i[1]
            return None

        def lvl(x):
            for i in x:
                if i[0] == "@netlevel":
                    return i[1]

        def net(x):
            for i in x:
                if i[0] == "@netmin":
                    return i[1]

        def is_net(x):
            i = field(x, "cidr")
            if i is not None:
                return True
            return False

        def obj(x):
            d = {}
            for k, v in x:
                if k in d:
                    d[k].append(v)
                else:
                    d[k] = [v]
            return d

        inet = None
        first = True
        for n in sorted(sorted(lis, key=lvl), key=net):
            o = obj(n)

            if is_net(n):
                if not first:
                    print()
                first = True
                inet = o
                continue

            ilvl = int(inet["@netlevel"][0])
            rlvl = int(o["@netlevel"][0])

            if ilvl + 1 != rlvl:
                print(
                    "\nNo Parent > ",
                    o["route"][0],
                    " ",
                    rlvl,
                    " ",
                    ",".join(o["mnt-by"]),
                    "Nearest INET ",
                    inet["cidr"][0],
                    " ",
                    ilvl,
                    " ",
                    ",".join(inet["mnt-by"]),
                )

                first = True
                continue

            if inet["@netmin"][0] > o["@netmin"][0] or inet["@netmax"][0] < o["@netmax"][0]:
                print(
                    "\nNo Parent > ",
                    o["route"][0],
                    " ",
                    rlvl,
                    " ",
                    ",".join(o["mnt-by"]),
                    "Nearest INET ",
                    inet["cidr"][0],
                    " ",
                    ilvl,
                    " ",
                    ",".join(inet["mnt-by"]),
                )

                first = True
                continue


if __name__ == "__main__":
    run(get_args())
