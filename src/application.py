#!/bin/python2

from io import StringIO, BytesIO
from configparser import NoSectionError, ParsingError
from datetime import datetime
import xml.etree.ElementTree as ET
from flask import Flask, redirect, url_for, render_template, request, Response
import clash_util_v2 as cutil

app = Flask(__name__)
app.config['ERROR'] = ''
app.config['MAX_CONTENT_LENGTH'] = 250*1024*1024  # Allows up to 250 MB


@app.route('/')
def index():
    now = datetime.now()
    filename = '_'.join(['clash_group', now.strftime('%Y-%m-%d-%H%M')])
    error = app.config['ERROR']
    app.config['ERROR'] = ''
    with open('./clash_util.ini', 'r') as conf_file:
        lens = [len(line) for line in conf_file]
        if len(lens) > 1:
            cols = max(lens) + 5
            rows = len(lens) + 2
        else:
            cols = 25
            rows = 9
        conf_file.seek(0)
        return render_template('form-gui.html', conf=conf_file,
                               rows=rows, cols=cols,
                               filename=filename, error=error)


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        # Get clashresults XML file and handle no file / wrong extension
        clashtest_file = request.files['uploadfile']
        if (not clashtest_file):
            app.config['ERROR'] = 'No clash file was uploaded'
            return redirect(url_for('index'))
        if (not clashtest_file.filename.lower().endswith('.xml')):
            app.config['ERROR'] = 'Uploaded file was not an XML file'
            return redirect(url_for('index'))

        # Try to parse the XML file, handle ParseError exception
        try:
            xml_root = ET.parse(clashtest_file).getroot()
        except ET.ParseError:
            app.config['ERROR'] = """There were problems parsing your XML
            file. Check your XML file and make sure there is nothing unusual.
            """
            return redirect(url_for('index'))

        # Get path config from file or textarea (uses file if file)
        configfile = request.files['configfile'].read().decode('utf-8')
        textarea = request.form['defaultconf']
        configfile_ptr = StringIO(configfile if configfile else textarea)

        # Try to parse path conf, handle NoSectionError or ParsingError
        try:
            path_order = cutil.getPathOrder(configfile_ptr, file_pointer=True)
        except NoSectionError:
            app.config['ERROR'] = """No section in the config file named
            "path". Make sure that your path configuration
            resembles the defaults in the textarea below.
            """
            return redirect(url_for('index'))
        except ParsingError:
            app.config['ERROR'] = """There were problems parsing your
            path configuration. Make sure that your path configuration
            resembles the defaults in the textarea below.
            """
            return redirect(url_for('index'))

        # Set up some additional output options
        toXLS = True if (request.form['output'] == 'xls') else False
        joinOnAttr = True if ('join' in request.form) else False
        outfile = BytesIO() if toXLS else StringIO()

        # Handle non-numeric and negative boxsize
        try:
            box_size = float(request.form['boxsize'])
        except ValueError:
            app.config['ERROR'] = """Box Size given was not a number.
            Try again.
            """
            return redirect(url_for('index'))
        if box_size < 0:
            app.config['ERROR'] = """Box Size given was a negative number.
            Try again.
            """
            return redirect(url_for('index'))

        # Try to get results, handle Missing Path or other exception
        try:
            cutil.writeClashResults(outfile, xml_root, path_order,
                                    toXLS, joinOnAttr, box_size)
        except cutil.MissingPath as mp:
            app.config['ERROR'] = """Missing path in the path configuration.
            Include one of these paths to your path configuration: %s
            """ % ', '.join(mp.paths)
            return redirect(url_for('index'))
        except:
            app.config['ERROR'] = """Unexpected error. Check your input
            and settings to make sure there is nothing unusual.
            """
            return redirect(url_for('index'))

        # Return the results
        outfile.seek(0)
        outfilename = request.form['outfilename']
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
