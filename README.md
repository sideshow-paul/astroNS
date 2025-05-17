# Aerospace astroNS:

The Aerospace astronS project has been developed by the Jacobs Engineering group and is available for individuals to be
modified for specific scenarios. The Framework can be used to create simulators of various domains and connect them
together. The simulators created by the framework are models of systems (actors) connected together that react to
messages sent to each other to simulate complex processes/network flow/behaviours.

Documentation on the software can be found at the following link (__insert_link__) or built locally using the sphinx.

_ _ _ _

## Sphinx Auto-Documentation

Using Sphinx, documentation can be auto generated from all docstring inside the project. Each function and class within 
the python file has a description of its purpose along with a description of the parameters and the return if 
applicable. The documentation is created into an HTML file that can be viewed within a web-browser. There is easy 
navigation to find each container, class and function within.

### Creating the HTML

When generating the auto-documentation HTML, run following commands in the terminal under the docs folder:
``` bash
make clean
make html
```
The first line removes all documentation to make sure no errors occur when generating the HTML. the second line 
generates teh HTML pages and add all the documentation from the python files.
