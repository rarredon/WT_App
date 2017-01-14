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
app.config['MAX_CONTENT_LENGTH'] = 250*1024*1024  # Allows up to 250 MB


@app.route('/')
def index():
    if 'DEFAULTS_SET' not in app.config:
        set_defaults()
    # Store error, if any
    error = app.config['ERROR']
    errorstep = app.config['ERRORSTEP']
    # Gets path configuration from clash_util file or previous setting
    pathconf = app.config['PATHCONF']
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
    filename = app.config['OUTFILENAME']
    return render_template('form-gui.html', conf=pathconf,
                           rows=rows, cols=cols, boxsize=boxsize,
                           toXLS=toXLS, joinOnAttr=joinOnAttr,
                           filename=filename, error=error, errorstep=errorstep)


def set_defaults(errorstep=0):
    """Sets defaults for the web app form

    Keyord Arguments:
      errorstep -- The step of the form in which the error was detected;
        errorstep=0 means no error (used to initialize configurations);
        errorstep=-1 means an unexpected error (restore all defaults)
    """
    # Record the defaults were set
    app.config['DEFAULTS_SET'] = True
    # Set default path configuration from clash_util.ini file
    if errorstep == 0 or errorstep == 2 or errorstep == -1:
        conf_filename = ('%s/clash_util.ini' %
                         os.path.dirname(os.path.realpath(__file__)))
        with open(conf_filename, 'r') as conf_file:
            app.config['PATHCONF'] = conf_file.read()
    if errorstep == 0 or errorstep == 3 or errorstep == -1:
        # Set default boxsize = 3.0
        app.config['BOXSIZE'] = 3.0
        # Set csv as default output
        app.config['TOXLS'] = False
        # Don't join groups on attr by default
        app.config['JOINONATTR'] = False
        # Default outfilename is clash_group_{current date/time}.ext
        now = datetime.now()
        filename = '_'.join(['clash_group', now.strftime('%Y-%m-%d-%H%M')])
        app.config['OUTFILENAME'] = filename
        # Default error message is empty string and errorstep is 0 (no error)
    app.config['ERROR'] = ''
    app.config['ERRORSTEP'] = 0


@app.route('/defaults/')
@app.route('/defaults/<int:errorstep>')
def restore_defaults(errorstep):
    set_defaults(errorstep)
    return redirect(url_for('index'))


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        # Stores form configurations to app config
        app.config['PATHCONF'] = request.form['defaultconf']
        app.config['BOXSIZE'] = request.form['boxsize']
        app.config['JOINONATTR'] = ('join' in request.form)
        app.config['TOXLS'] =  (request.form['output'] == 'xls')
        app.config['OUTFILENAME'] = request.form['outfilename']

        # Get clashresults XML file and handle no file / wrong extension
        clashtest_file = request.files['uploadfile']
        if (not clashtest_file):
            app.config['ERROR'] = 'No clash file was uploaded'
            app.config['ERRORSTEP'] = 1
            return redirect(url_for('index'))
        if (not clashtest_file.filename.lower().endswith('.xml')):
            app.config['ERROR'] = 'Uploaded file was not an XML file'
            app.config['ERRORSTEP'] = 1
            return redirect(url_for('index'))

        # Try to parse the XML file, handle ParseError exception
        try:
            xml_root = ET.parse(clashtest_file).getroot()
        except ET.ParseError:
            app.config['ERROR'] = """There were problems parsing your XML
            file. Check your XML file and make sure there is nothing unusual.
            """
            app.config['ERRORSTEP'] = 1
            return redirect(url_for('index'))

        # Get path config from file or textarea (uses file if file)
        configfile = request.files['configfile'].read().decode('utf-8')
        if configfile:
            app.config['PATHCONF'] = configfile
        configfile_ptr = StringIO(app.config['PATHCONF'])

        # Try to parse path conf, handle NoSectionError or ParsingError
        try:
            path_order = cutil.getPathOrder(configfile_ptr, file_pointer=True)
        except NoSectionError:
            app.config['ERROR'] = """No section in the config file named
            "path". You can edit your configuration in Step Two below.
            """
            app.config['ERRORSTEP'] = 2
            return redirect(url_for('index'))
        except ParsingError:
            app.config['ERROR'] = """There were problems parsing your
            path configuration. You can edit your configuration in Step 
            Two below.
            """ 
            app.config['ERRORSTEP'] = 2
            return redirect(url_for('index'))
        except DuplicateOptionError as doe:
            app.config['ERROR'] = """The option '%s' appears more than once in
            your path configuration. Each option should appear only
            once. You can edit your configuration in Step Two below.
            """ % doe.option
            app.config['ERRORSTEP'] = 2
            return redirect(url_for('index'))
        # Set up some additional output options
        toXLS = app.config['TOXLS']
        joinOnAttr = app.config['JOINONATTR']
        outfile = BytesIO() if toXLS else StringIO()
        # Handle non-numeric and negative boxsize
        try:
            box_size = float(app.config['BOXSIZE'])
        except ValueError:
            app.config['ERROR'] = """Box Size given was not a number.
            Try a to use a number instead.
            """
            app.config['ERRORSTEP'] = 3
            return redirect(url_for('index'))
        if box_size < 0:
            app.config['ERROR'] = """Box Size given was a negative number.
            Try a positive number instead.
            """
            app.config['ERRORSTEP'] = 3
            return redirect(url_for('index'))

        # Try to get results, handle Missing Path or other exception
        try:
            cutil.writeClashResults(outfile, xml_root, path_order,
                                    toXLS, joinOnAttr, box_size)
        except cutil.MissingPath as mp:
            app.config['ERROR'] = """Missing path in the path configuration.
            Include one of these paths to your path configuration: %s
            """ % ', '.join(mp.paths)
            app.config['ERRORSTEP'] = 2
            return redirect(url_for('index'))
        except:
            app.config['ERROR'] = """Unexpected error. Check your input
            and settings to make sure there is nothing unusual.
            """
            app.config['ERRORSTEP'] = -1
            return redirect(url_for('index'))

        # Return the results
        outfile.seek(0)
        outfilename = app.config['OUTFILENAME']
        if not outfilename:
            now = datetime.now()
            outfilename = '_'.join(['clash_group',
                                    now.strftime('%Y-%m-%d-%H%M')])
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
