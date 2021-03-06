#!/bin/python3
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
# Email: ryan.c.arredondo@gmail.com
# Date: October 2016
# ----------------------------------------------------------------------
# Updates: (Who/When/What)
#   Ryan / 03-17-17 / Refactoring the joinOnAttr function to make it
#                     more readable and efficient
#   Ryan / 04-21-17 / Default arg to getCommandLineArgs changed to None
#   Ryan / 05-09-17 / getPathOrder sorted keys lexicographically which
#                     was undesirable; now uses order given in ini file
#   Matt / 06-22-17 / Added X,Y,Z Coordinate in the writeClashResults
#                     function
#   Ryan / 08-03-17 / Set idname, idval to None if clashobject has no
#                     objectattribute section; no joining is performed
#                     on these clash objects when -j option is set
#   Ryan / 08-07-17 / Changes to getGroups function to sort clashes by
#                     x coord first and then check for overlaps
#                     thereby reducing the number of iterations in
#                     quadratic algorithm to check overlaps
#   Ryan / 08-07-17 / Added quiet option with -q or --quiet
#   Ryan / 09-03-17 / Added functionality to split the contents of cells
#                     which exceed 32,767 chars
#   Ryan / 09-03-17 / Added option -n / --no-split to not split large
#                     cells (more than 32,767 chars); can only be used
#                     for CSV output; -x with -n will raise an error
# ----------------------------------------------------------------------

from argparse import ArgumentParser           # for command line parsing
from configparser import SafeConfigParser     # for file config parsing
import xml.etree.ElementTree as ET
import csv
import xlwt                                   # write to xls format

__version__ = '1.2.1'


def main():
    """Function called if run from command-line"""
    # Set up the configurations
    args = getCommandLineArgs()
    path_order = getPathOrder(args.config_file)
    xml_root = ET.parse(args.clash_file).getroot()
    write_opt = 'wb' if args.output_xls else 'w'
    with open(args.output_filename, write_opt) as outfile:
        writeClashResults(outfile, xml_root, path_order,
                          toXLS=args.output_xls,
                          joinOnAttr=args.join_on_attribute,
                          box_size=args.box_size,
                          quiet=args.quiet,
                          no_split=args.no_split)


def writeClashResults(outfile, clashroot, path_order, toXLS=False,
                      joinOnAttr=False, box_size=3.0, quiet=False,
                      no_split=False):
    """Writes the results of the clash grouping to outfile

    Keyword arguments:
      outfile -- a file or file-like object that is writeable
      clashroot -- the root of the XML clash test file
      path_order -- the path order configured in the .ini file
      toXLS -- output to XLS if True, else output to CSV
      joinOnAttr -- group clashes by entity handle / element ID if true
      box_size -- coord-wise distance between clashes for grouping
      quiet -- no output to stdout
      no_split -- do not split large cells if true; only if toXLS==False

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
              'Group Attribute Values',
              'X Coordinate',
              'Y Coordinate',
              'Z Coordinate',
              'Status']

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
        if not quiet:
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
                    if (type(contents) is str) and (len(contents) > 32767):
                        contents, continued = split_cell(contents, header[col])
                        ws.write(row, col, contents)
                        line.extend(continued)
                    else:
                        ws.write(row, col, contents)
                row += 1
            else:
                writer = csv.writer(outfile)
                if not no_split:
                    for col, cell in enumerate(line):
                        if (type(cell) is str) and (len(cell) > 32767):
                            cell, continued = split_cell(cell, header[col])
                            line[col] = cell
                            line.extend(continued)
                writer.writerow(line)

        if not quiet:
            print('Done with %s.' % testname)

    # Saves xls file if xls option was used
    if toXLS:
        wb.save(outfile)
    if not quiet:
        print('Finished all clashtests.')

def split_cell(contents, col):
    """Splits contents of a cell into chunks smaller than 32767 chars

    Keyword arguments:
      cell -- The contents of the cell that are to be split; assumes contents
              are comma separated and tries to split at commas.
      col -- Column name corresponding to the cell being split

    Returns:
      head -- str that will be written back to the cell of interest
      remains -- List of strs consisting of remaining chunks
    """
    cutoff = contents.rfind(',', 0, 32767)
    if cutoff == -1:  # Didn't find ',' substr; this shouldn't really happen
        cutoff = 32767
    head = contents[0:cutoff]
    remaining = contents[cutoff + 2:]  # + 2 skips the substr: ', '
    prefix = '(' + col + ' cont.) '
    prefixlen = len(prefix)
    remains = []
    while len(remaining) > (32767 - prefixlen):
        cutoff = remaining.rfind(',', 0, 32767-prefixlen)
        chunk = prefix + remaining[0:cutoff]
        remains.append(chunk)
        remaining = remaining[cutoff + 2:]  # + 2 skips the substr: ', '
    if remaining:
        remains.append(prefix + remaining)
    return head, remains


def getGroupInfo(ogClash, group, clashes):
    """Gets information to be output for the specified group

    Keyword arguments:
      ogClash -- the origin clash's guid (key for clashes dict)
      group -- a set of clash guids belonging to the same group
      clashes -- clash dict as returned by getClashes function
      xyzCoor -- the location of the clash in space
      status -- established if the clash is new or from a previous run

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
    groupAttrNames = ', '.join(name for name in groupNames if name is not None)
    groupAttrVals = ', '.join(val for val in groupVals if val is not None)
    xyzCoor = ogClash['coords']
    status = ogClash['status']

    return [ogClashName,
            clashGroupNames,
            groupCount,
            ogPathBlame,
            ogAttrName,
            ogAttrVal,
            groupAttrNames,
            groupAttrVals,
            xyzCoor[0],
            xyzCoor[1],
            xyzCoor[2],
            status]


def joinOnAttrValue(groups, clashes):
    """Joins clash groups whose clashes match on attribute/id value

    Keyword arguments:
      groups -- a dict of clash groups as returned by getGroups function
      clashes -- a dict of clashes as returned by getClashes function

    Returns:
      joinedGroups -- A dict of groups joined by attribute values. The
      key is the origin clash's guid and the value is a set of guids
      of clashes in that group.

    """
    joinedGroups = groups.copy()

    # Builds a lookup dictionary mapping attribute value to clashes
    # that possesses that attribute value
    idValToClashes = {}
    for key, clash in clashes.items():
        idVal = clash['objblame']['idval']
        if idVal is not None:
            idValToClashes.setdefault(idVal, []).append(key)

    # Builds a dict mapping each clash to a list of its origin clashes,
    # i.e., clashes c in groups.keys() for which clash belongs to groups[c]
    clashToOriginClashes = {}
    for originClash, group in joinedGroups.items():
        for clash in group:
            clashToOriginClashes.setdefault(clash, []).append(originClash)

    # Iterate over all attribute values and join the groups of origin clashes
    # that have clashes who match on attribute value
    for matchingClashes in idValToClashes.values():
        # Set to contain origin clashes whose groups have clashes with
        # attribute value = idVal
        originClashes = set()
        for clash in matchingClashes:
            originClashes.update(clashToOriginClashes[clash])
        joinUpdate(joinedGroups, originClashes, clashToOriginClashes)
    return joinedGroups


def joinUpdate(joinedGroups, originClashes, clashToOriginClashes):
    """Helper function for joinOnAttrValue that performs a join update

    Keyword arguments:
      -- joinedGroups: A dict containing groups of clashes being joined
      -- originClashes: List of keys for joinedGroups dict with groups to join
      -- clashToOriginClashes: mapping from clash to originClashes that gets
         updated according to updates for joinedGroups
    Returns:
      None; however, joinedGroups and clashToOriginClashes are altered

    """
    originClashCount = 0  # will be replaced on first run through loop
    joinedGroup = set()
    for clash in originClashes:
        group = joinedGroups[clash]
        joinedGroup.update(group)
        # Make origin clash the clash with largest group
        if len(group) > originClashCount:
            originClash = clash
            originClashCount = len(group)
    joinedGroups[originClash].update(joinedGroup)

    # Remove items from joinedGroups that were added to group for originClash
    # and update clashToOriginClashes mapping
    for clash in originClashes:
        if clash != originClash:
            for c in joinedGroups[clash]:
                clashToOriginClashes[c].remove(clash)
                if originClash not in clashToOriginClashes[c]:
                    clashToOriginClashes[c].append(originClash)
            del joinedGroups[clash]


def getGroups(clashes, bs):
    """Groups together clashes if they fall within boxsize, bs

    Keyword arguments:
    clashes -- a dict of clashes as returned by getClashes function
    bs -- the overlapping box size for clash points

    Returns:
      groups -- a dict of clash groups that are joined if the clash's
      xyz coords are within the boxsize. The key is the origin clash's
      guid and the value is a set of guids of clashes in that group.

    """
    # Return empty dict if no clashes (clashes == empty dict)
    if not clashes:
        return {}

    # Initializes each group with its origin clash
    groups = dict([(key, set([key])) for key in clashes])

    # Sort the clashes by x coordinate
    sortedclashes = sorted(clashes.items(), key=lambda c: c[1]['coords'][0])

    # Iterate over clashes and check nearby clashes if x2-x1 <= boxsize
    # and then if clashes overlap and react accordingly
    for idx, (key1, clash1) in enumerate(sortedclashes):
        idx += 1
        try:
            key2, clash2 = sortedclashes[idx]
        except IndexError:  # idx > len(list); we went too far!
            break
        x1 = clash1['coords'][0]
        x2 = clash2['coords'][0]
        while (x2 - x1) <= bs:
            if clashesOverlap(clash1, clash2, bs):
                groups[key1].add(key2)
                groups[key2].add(key1)
            idx += 1
            try:
                key2, clash2 = sortedclashes[idx]
            except IndexError:  # idx > len(list); we went too far!
                break
            x2 = clash2['coords'][0]

    # Removes groups that are duplicates or subsets of another group
    deletes = []
    for key, group in groups.items():
        # Ignore already deleted and origin clash
        checkKeys = group.difference(deletes, [key])

        # Set difference is empty if group is duplicate or subset
        # (bool = False if set difference is empty, else bool = True)
        isDupOrSub = not all(bool(group.difference(groups[k]))
                             for k in checkKeys)
        if isDupOrSub:
            deletes.append(key)
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
        guid = clash.get('guid')  # A unique identifier
        status = clash.get('status')
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
                         'objblame': objblame,
                         'status': status}
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
        else:
            idname = None
            idval = None
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
    parser = SafeConfigParser(allow_no_value=True, strict=True)
    parser.optionxform = str  # Makes key values case sensitive
    if file_pointer:
        parser.readfp(config_file)
    else:
        parser.read(config_file)

    # Get values if "key=value" pair, else get key (w/ no value)
    path_config = [val if val else key for s in parser.sections()
                   for key, val in parser.items(s)]
    return path_config


def getCommandLineArgs(arglist=None):
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
    parser.add_argument('-o', '--output-filename',
                        default='clash_group',
                        help='Name of file to output')
    parser.add_argument('-j', '--join-on-attribute', action='store_true',
                        help='Joins clashes by entity handle or Element ID')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='No output written to stdout')
    group = parser.add_mutually_exclusive_group()
    # The following options conflict with each other
    group.add_argument('-x', '--output-xls', action='store_true',
                       help='Output an Excel xls file')
    group.add_argument('-n', '--no-split', action='store_true',
                       help='Don\'t split cells > 32767 chars')

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
