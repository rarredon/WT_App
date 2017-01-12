# WT_App

This repository contains the source code of a web app for grouping clashes.

The contents (with a short description) are as follows.

src/
|-- application.py      * Code for web app (uses Flask web application framework)
|-- clash_util.ini      * Contains the default path configuration used by the app
|-- clash_util_v2.py    * Code for grouping the clashes and outputting the results
|-- requirements.txt    * List of required libraries as ouput by 'python -m pip freeze'
|-- static
    |-- favicon.ico     * Whiting Turner icon
  `````-- styles.css      * CSS file describing styles used in web app
\-- templates
  `````-- form-gui.html   * HTML template (Jinja2) describing html form in web app
