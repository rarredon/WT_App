# WT_App

This repository contains the source code of a web app for grouping clashes.

The contents (with a short description) are as follows.

```
src/
|--.ebextensions
   `-- 01_files.config    * Configuration file for Amazon Web Services
|-- application.py        * Code for web app (uses Flask web application framework)
|-- application_local.py  * Code for running web app locally
|-- app.yaml		        * Configuration file for Google App Engine
|-- clash_util.ini        * Contains the default path configuration used by the app
|-- clash_util_v2.py      * Code for grouping the clashes and outputting the results
|-- requirements.txt      * List of required Python libraries as ouput by 'python -m pip freeze'
|-- static
    |-- favicon.ico       * Whiting Turner icon
    `-- styles.css        * CSS file describing styles used in web app
\-- templates
    `-- form-gui.html     * HTML template (Jinja2) describing html form in web app
 
 INSTRUCTIONS.txt       * Instructions for running the app locally
 SETUP.bat              * Batch executable for setting up the app (downloads requirements)
 RUN.bat                * Batch executable for running the app
```
