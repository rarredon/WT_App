#!bin/python
# ----------------------------------------------------------------------
# clash_util_v2.py
# ----------------------------------------------------------------------
# Purpose: A program to group clashes that fit within a specified box
#   size (default = 3.0 ft) and also group by entity handle / element
#   ID. Imports of this program can make calls to the writeClashResults
#   function after configuring the outfile, the root of the input xml
#   file (clashroot), and the configured path order as specified in .ini
#   file (path_order).
# Input: XML file with clash test results
# Output: CSV or XLS file with clash groups
# Author: Ryan Arredondo
# Email: sucharyan@gmail.com
# Date: October 2016
# ----------------------------------------------------------------------
# Updates: (Who/When/What)
#
# ----------------------------------------------------------------------

from argparse import ArgumentParser           # for command line parsing
from configparser import SafeConfigParser     # for file config parsing
import xml.etree.ElementTree as ET
import csv
import xlwt


def main():
    # Set up the configurations
    args = getCommandLineArgs()
    path_order = getPathOrder(args.config_file)
    xml_root = ET.parse(args.clash_file).getroot()
    write_opt = 'wb' if args.output_xls else 'w'
    with open(args.output_filename, write_opt) as outfile:
        writeClashResults(outfile, xml_root, path_order,
                          toXLS=args.output_xls,
                          joinOnAttr=args.join_on_attribute,
                          box_size=args.box_size)


def writeClashResults(outfile, clashroot, path_order,
                      toXLS=False, joinOnAttr=False, box_size=3.0):
    """Writes the results of the clash grouping to outfile

    Keyword arguments:
      outfile -- a file or file-like object that is writeable
      clashroot -- the root of the XML clash test file
      path_order -- the path order configured in the .ini file
      toXLS -- output to XLS if True, else output to CSV
      joinOnAttr -- group clashes by entity handle / element ID if true

    """
    # The columns that will be written to output
    header = ['Clash Test',
              'Origin Clash',
              'Clash Group',
              'Group Count',
              'Origin Path Blame',
              'Origin Attribute Name',
              'Origin Attribute Value',
              'Group Attribute Names',
              'Group Attribute Values']

    # Initializes outputs
    if toXLS:
        row = 0
        wb = xlwt.Workbook()
        ws = wb.add_sheet('Clash Groups')
        for col, contents in enumerate(header):
            ws.write(row, col, contents)
        row += 1
    else:
        writer = csv.writer(outfile)
        writer.writerow(header)

    # Iterate over each clash test and output the results
    for clashtest in clashroot.iter('clashtest'):
        testname = clashtest.get('name')
        print('Working on %s...' % testname)
        clashes = getClashes(clashtest, path_order)
        clashGroups = getGroups(clashes, box_size)
        if joinOnAttr:
            clashGroups = joinOnAttrValue(clashGroups, clashes)

        for ogClash, clashGroup in clashGroups.items():
            line = [testname]
            groupInfo = getGroupInfo(ogClash, clashGroup, clashes)
            line.extend(groupInfo)
            if toXLS:
                for col, contents in enumerate(line):
                    ws.write(row, col, contents)
                row += 1
            else:
                writer = csv.writer(outfile)
                writer.writerow(line)
        print('Done with %s.' % testname)
    # Saves xls file if xls option was used
    if toXLS:
        wb.save(outfile)
    print('Finished all clashtests.')


def getGroupInfo(ogClash, group, clashes):
    """Gets information to be output for the specified group

    Keyword arguments:
      ogClash -- the origin clash's guid (key for clashes dict)
      group -- a list of clash guids belonging to the same group
      clashes -- clash dict as returned by getClashes function

    Returns:
      A list containing the contents of one row being written to output

    """
    # These are intermediate variables
    ogClash = clashes[ogClash]
    clashGroup = [clashes[clash] for clash in group]
    groupNames = set(clash['objblame']['idname'] for clash in clashGroup)
    groupVals = set(clash['objblame']['idval'] for clash in clashGroup)

    # This is the info that is printed to one row of the file
    ogClashName = ogClash['name']
    clashGroupNames = ', '.join(clash['name'] for clash in clashGroup)
    groupCount = len(clashGroup)
    ogPathBlame = ogClash['pathblame']
    ogAttrName = ogClash['objblame']['idname']
    ogAttrVal = ogClash['objblame']['idval']
    groupAttrNames = ', '.join(groupNames)
    groupAttrVals = ', '.join(groupVals)

    return [ogClashName,
            clashGroupNames,
            groupCount,
            ogPathBlame,
            ogAttrName,
            ogAttrVal,
            groupAttrNames,
            groupAttrVals]


def joinOnAttrValue(groups, clashes):
    """Joins clash groups whose clashes match on attribute value

    Keyword arguments:
      groups -- a dict of clash groups as returned by getGroups function
      clashes -- a dict of clashes as returned by getClashes function

    Returns:
      joinedGroups -- A dict of groups joined by attribute values. The
      key is the origin clash's guid and the value is a list of guids
      of clashes in that group.

    """
    # Builds a lookup dictionary mapping attribute value to clashes
    # with that possesses that attribute value
    attrValsToClash = {}
    for key, clash in clashes.items():
        attrVal = clash['objblame']['idval']
        attrValsToClash.setdefault(attrVal, []).append(key)

    # Now we begin the joining
    skip = []
    joinedGroups = {}
    for clash, group in groups.items():
        if clash in skip:  # Clash was already joined with another group
            continue
        clashGroup = [clashes[clash] for clash in group]
        joinKeys = set(clash['objblame']['idval'] for clash in clashGroup)
        joinedOn = set()
        ogClash = clash
        ogClashCount = len(group)
        joinedGroup = set(group)
        while joinKeys:
            joinedOn.update(joinKeys)
            # Join groups on each key
            for joinKey in list(joinKeys):
                for joinClash in attrValsToClash[joinKey]:
                    if joinClash not in groups:
                        # Find ogClash whose group contains joinClash
                        for key, grp in groups.items():
                            if joinClash in grp:
                                joinClash = key
                                break
                    joinGroup = groups[joinClash]
                    joinCount = len(joinGroup)
                    joinedGroup = joinedGroup.union(joinGroup)
                    if joinCount > ogClashCount:
                        ogClash = joinClash
                        ogClashCount = joinCount

                    # Update join keys with any new keys
                    clashGroup = [clashes[clash] for clash in joinGroup]
                    joinKeys.update(clash['objblame']['idval']
                                    for clash in clashGroup)

                    # No longer need to consider this clash
                    skip.append(joinClash)

            # Remove joinKeys that have already been joined on
            joinKeys.difference_update(joinedOn)
        joinedGroups[ogClash] = list(joinedGroup)
    return joinedGroups


def getGroups(clashes, bs):
    """Groups together clashes if they fall within boxsize, bs

    Keyword arguments:
    clashes -- a dict of clashes as returned by getClashes function
    bs -- the overlapping box size for clash points

    Returns:
      groups -- a dict of clash groups that are joined if the clash's
      xyz coords are within the boxsize. The key is the origin clash's
      guid and the value is a list of guids of clashes in that group.

    """
    # Initializes each group with its origin clash
    groups = dict([(key, [key]) for key in clashes])
    for key1, clash1 in clashes.items():
        for key2, clash2 in clashes.items():
            if (key1 != key2 and
                    clashesOverlap(clash1, clash2, bs)):
                groups[key1].append(key2)

    # Removes groups that are duplicates or subsets of another group
    deletes = []
    for key1, group in groups.items():
        groupSet = set(group)

        # Ignore already deleted and origin clash
        keys = groupSet.difference(deletes, [key1])

        # Set difference is empty if group is duplicate or subset
        # (bool = False if set difference is empty, else bool = True)
        isDupOrSub = not all(bool(groupSet.difference(groups[key2]))
                             for key2 in keys)
        if isDupOrSub:
            deletes.append(key1)
    for key in deletes:
        del groups[key]
    return groups


def clashesOverlap(c1, c2, bsize):
    """True/False: if clash coordinates overlap according to box size

    Keyword arguments:
      c1 -- clash 1 info
      c2 -- clash 2 info
      bsize -- coordinate-wise limit on whether two clashes overlap

    Returns:
      True if they overlap, else False

    """
    x1, y1, z1 = c1['coords']
    x2, y2, z2 = c2['coords']
    if (abs(x1-x2) <= bsize and abs(y1-y2) <= bsize and abs(z1-z2) <= bsize):
        return True
    return False


def getClashes(test, paths):
    """Gets the clash results present in a clashtest

    Keyword arguments:
      test -- an XML element with the clashtest tag
      paths -- ordered list (configured by user) containing blame paths

    Returns:
      clashes -- a dict whose key is a clashresults' guid and
      value is a dict with clash name, coordinates, file path
      being blamed, and object associated with pathblame: a dict
      obtained from getClashObjects function

    """
    clashes = {}
    clashresults = test.find('clashresults')
    for clash in clashresults.findall('clashresult'):
        # Some info about the clash
        name = clash.get('name')
        guid = clash.get('guid')    # A unique identifier
        coords = getClashCoords(clash)
        clashobjects = getClashObjects(clash)
        clashpaths = [obj['pathfile'] for obj in clashobjects]

        # Find path to blame
        for path in paths:
            # Check if path is substr of any clashpaths
            path_in_object = list(map(lambda clashpath: path in clashpath,
                                      clashpaths))
            if any(path_in_object):
                idx = path_in_object.index(True)
                break
        else:  # No path in any of the objects
            raise MissingPath(clashpaths)

        objblame = clashobjects[idx]
        pathblame = objblame['pathfile']

        # Assert should never be triggered; doesn't hurt to check
        assert guid not in clashes.keys(), \
            'guid is not unique to clash: %s' % name
        clashes[guid] = {'name': name,
                         'coords': coords,
                         'pathblame': pathblame,
                         'objblame': objblame}
    return clashes


class MissingPath(Exception):
    """Raised when a clash's paths are not found in the conf file

    Keyword arguments:
    paths -- Clash's paths which were not found in the conf file

    """
    def __init__(self, paths):
        self.paths = paths

    def __str__(self):
        return repr(self.paths)


def getClashObjects(clash):
    """Gets the clash objects of a clash

    Keyword arguments:
      clash -- an XML element with the clashresult tag

    Returns:
      objects -- a list of clash object children of the parent
      clashresult; the clash object children are dicts with identifier
      name (entity handle / element id), identifier value, and origin
      file path

    """
    objects = []
    clashobjects = clash.find('clashobjects')
    for obj in clashobjects.findall('clashobject'):
        attribs = obj.find('objectattribute')
        if attribs is not None:  # Which it sometimes is for some reason
            idname = attribs.find('name').text
            idval = attribs.find('value').text
        pathlink = obj.find('pathlink')
        pathfile = pathlink[2].text
        objects.append({'idname': idname,
                        'idval': idval,
                        'pathfile': pathfile})
    return objects


def getClashCoords(clash):
    """Returns the x,y,z coords of clash

    Keyword arguments:
    clash -- an XML element with the clashresult tag

    """
    clashpoint = clash.find('clashpoint')
    pos = clashpoint.find('pos3f')
    return (float(pos.get('x')), float(pos.get('y')), float(pos.get('z')))


def getPathOrder(config_file, file_pointer=False):
    """Get path blame precedence from the config file

    Keyword arguments:
      config_file -- path to config file or file (if file_pointer=True)
      file_pointer -- if True, config_file should be file or file-like

    Returns:
      Returns a list with the path blame precedence as configured in
      the path configuration (.ini) file

    """
    # Initialize parser and read in the configurations
    parser = SafeConfigParser()
    if file_pointer:
        parser.readfp(config_file)
    else:
        parser.read(config_file)

    # Sorts key=value entries in [path] section alphanumerically by key
    path_config = sorted(parser.items('path'), key=lambda pair: pair[0])

    # Get only values from sorted key=value entries in [path]
    return [path_file_name for _, path_file_name in path_config]


def getCommandLineArgs(arglist=[]):
    """Sets up argument parser and gets command line arguments

    Keyword arguments:
      arglist (optional) -- parses arglist as command line arguments.
        If arglist is not set, parses arguments on the command line.

    Returns:
      args -- a namespace containing the command line arguments
    """
    # initializes the parser instance
    parser = ArgumentParser(description='Groups the clashes from a'
                            ' Navisworks clash test XML file.')

    # a mandatory argument: the clash file
    parser.add_argument('clash_file', metavar='CLASH_FILE',
                        help='Clash XML file')

    # some optional arguments
    parser.add_argument('-c', '--config-file',
                        default='clash_util.ini',
                        help='Configuration file to use')
    parser.add_argument('-b', '--box-size', type=float,
                        default=3.0,
                        help='Size of the box in feet')
    parser.add_argument('-x', '--output-xls', action='store_true',
                        help='Output an Excel xls file')
    parser.add_argument('-o', '--output-filename',
                        default='clash_group',
                        help='Name of file to output')
    parser.add_argument('-j', '--join-on-attribute', action='store_true',
                        help='Joins clashes by entity handle or Element ID')

    # parse the arguments and handle the file extension
    args = parser.parse_args(arglist) if arglist else parser.parse_args()
    if args.output_xls:
        if not args.output_filename.endswith('.xls'):
            args.output_filename += '.xls'
    else:
        if not args.output_filename.endswith('.csv'):
            args.output_filename += '.csv'
    return args


if __name__ == "__main__":
    main()
