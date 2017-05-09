#!/bin/python
# ----------------------------------------------------------------------
# application.py
# ----------------------------------------------------------------------
# Purpose: Code for the clash grouper web application
# Author: Ryan Arredondo
# Email: ryan.c.arredondo@gmail.com
# Date: October 2016
# ----------------------------------------------------------------------
# Updates: (Who - When - What)
#   Ryan - 1/14/17 - Added handling for DuplicateOptionError and 
#     resolved an issue with application being run from a directory other
#     than the current directory using os.path.dir and os.path.realpath.
#   Ryan - 1/14/17 - Form configurations will no longer be reset upon
#     triggering an error. Instead, user will be presented with the
#     option to restore the default configurations for step where error
#     occurred.
# ----------------------------------------------------------------------

from io import StringIO, BytesIO
from configparser import NoSectionError, ParsingError, DuplicateOptionError
from datetime import datetime
import os.path
import xml.etree.ElementTree as ET
from flask import Flask, redirect, url_for, render_template, request, Response
import clash_util_v2 as cutil

app = Flask(__name__)
app.config.from_object(__name__)

app.config.update(dict(
    MAX_CONTENT_LENGTH = 250*1024*1024,  # Allows up to 250 MB
    PATHCONFFILENAME = '%s/clash_util.ini' %
                         os.path.dirname(os.path.realpath(__file__)),
    BOXSIZE = 3.0,
    TOXLS = False,
    JOINONATTR = False
))


@app.route('/')
def index():
    # Gets path configuration from clash_util.ini file
    with open(app.config['PATHCONFFILENAME'], 'r') as pathconffile:
        pathconf = pathconffile.read()
    # Gets columns and rows of pathconf to size the textarea
    num_lines = pathconf.count('\n')
    max_width = max(len(line) for line in pathconf.split('\n'))
    if num_lines > 1:
        cols = max_width + 5
        rows = num_lines + 2
    else:
        cols = 25
        rows = 9
    # Gets the remaining settings
    boxsize = app.config['BOXSIZE']
    toXLS = app.config['TOXLS']
    joinOnAttr = app.config['JOINONATTR']
    # Set the default outfilename
    now = datetime.now()
    outfilename = '_'.join(['clash_group', now.strftime('%Y-%m-%d-%H%M')])
    return render_template('form-gui.html', conf=pathconf,
                           rows=rows, cols=cols, boxsize=boxsize,
                           toXLS=toXLS, joinOnAttr=joinOnAttr,
                           outfilename=outfilename, infilename='',
                           error='', errorstep=0)


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        # Step 1
        clashtest_file = request.files['uploadfile']
        infilename = clashtest_file.filename
        # Step 2
        pathconf = request.form['defaultconf']
        configfile = request.files['configfile'].read().decode('utf-8')
        if configfile:  # Path conf file takes precedence over textarea
            pathconf = configfile
        num_lines = pathconf.count('\n')
        max_width = max(len(line) for line in pathconf.split('\n'))
        if num_lines > 1:
            cols = max_width + 5
            rows = num_lines + 2
        else:
            cols = 25
            rows = 9
        configfile_ptr = StringIO(pathconf)
        # Step 3
        boxsize = request.form['boxsize']
        joinOnAttr = ('join' in request.form)  # True if checked else False
        toXLS =  (request.form['output'] == 'xls')
        outfilename = request.form['outfilename']

        ## Assume for now there is no error
        error = ''
        errorstep = 0

        ## Get clashresults XML file (Step 1) and find any issues in Step 1

        # Was there even a file?
        if (not clashtest_file):
            error = 'No clash file was uploaded.'
        # Was it an XML file?
        elif (not clashtest_file.filename.lower().endswith('.xml')):
            error = 'Uploaded file was not an XML file.'
        else:
            # Is the XML file parsable?
            try:
                xml_root = ET.parse(clashtest_file).getroot()
            except ET.ParseError:
                error = """There were problems parsing your XML file. Check 
                your XML file and make sure there is nothing unusual.
                """
        if error:
            return render_template('form-gui.html', conf=pathconf,
                                   rows=rows, cols=cols, boxsize=boxsize,
                                   toXLS=toXLS, joinOnAttr=joinOnAttr,
                                   outfilename=outfilename,
                                   error=error, errorstep=1)
            
        ## Get path configuration (Step 2) and find any issues in Step 2
        try:
            path_order = cutil.getPathOrder(configfile_ptr, file_pointer=True)
        except NoSectionError:
            error = """No section found in the ini file. Edit your
            path configuration in Step Two below so that [SECTION] is at the
            beginning  of the file.
            """
        except ParsingError:
            error = """There were problems parsing your path configuration. 
            You can edit your configuration in Step Two below.
            """ 
        except DuplicateOptionError as doe:
            error = """The option '%s' appears more than once in section 
            '[%s]' of your path configuration. Each option should appear only
            once. You can edit your configuration in Step Two below.
            """ % (doe.option, doe.section)
        except:
            error = """There were unexpected errors in you path configuration.
            You can edit your configuration in Step Two below.
            """
        if error:
            return render_template('form-gui.html', conf=pathconf,
                                   rows=rows, cols=cols, boxsize=boxsize,
                                   toXLS=toXLS, joinOnAttr=joinOnAttr,
                                   outfilename=outfilename,
                                   error=error, errorstep=2)

        ## Get remaining settings and check that boxsize is a positive number
        outfile = BytesIO() if toXLS else StringIO()
        try:
            boxsize = float(boxsize)
            if boxsize < 0:
                error = """Box Size given was a negative number. Try a 
                positive number instead.
                """
        except ValueError:
            error = """Box Size given was not a number.
            Try a to use a number instead.
            """
        if error:
            return render_template('form-gui.html', conf=pathconf,
                                   rows=rows, cols=cols, boxsize=boxsize,
                                   toXLS=toXLS, joinOnAttr=joinOnAttr,
                                   outfilename=outfilename,
                                   error=error, errorstep=3)

        # Try to get results, handle Missing Path or other exception
        try:
            cutil.writeClashResults(outfile, xml_root, path_order,
                                    toXLS, joinOnAttr, boxsize)
        except cutil.MissingPath as mp:
            error = """Missing path in the path configuration.
            Include one of these paths to your path configuration: %s.
            """ % ', '.join(mp.paths)
            errorstep = 2
        except:
            error = """Unexpected error. Check your input
            and settings to make sure there is nothing unusual.
            """
            errorstep = 0
        if error:
            return render_template('form-gui.html', conf=pathconf,
                                   rows=rows, cols=cols, boxsize=boxsize,
                                   toXLS=toXLS, joinOnAttr=joinOnAttr,
                                   outfilename=outfilename,
                                   error=error, errorstep=errorstep)

        # Finally, return the results
        outfile.seek(0)
        if not outfilename:
            outfilename = ('clash_group_%s' %
                           datetime.now().strftime('%Y-%m-%d-%H%M'))
        if toXLS and not outfilename.lower().endswith('.xls'):
            outfilename = '.'.join([outfilename, 'xls'])
        elif not toXLS and not outfilename.lower().endswith('.csv'):
            outfilename = '.'.join([outfilename, 'csv'])
        mimetype = 'application/vnd.ms-excel' if toXLS else 'text/csv'
        return Response(outfile.read(), mimetype=mimetype,
                        headers={'Content-disposition':
                                 ('attachment; filename=%s' % outfilename)})
    # /Submit was reached by GET method
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0')
