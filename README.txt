##### parse kindle txt file is BROKEN after fixing the added page number in the new kindle highlights export html!! #####

Ignores non-highlight clippings.

Needs to create a new note type named "Basic-Kindle" which has the field names
"Front"
"Back"
"Author"
"Book Title"
"Highlight Type"
"Page and Location"
"Section"
"Subsection"

Else script will break!!

The original breaks with the new kindle html which includes the page number. (__init__.pyoldoriginal)

The __init__ copy fixed version.py works, but lumps all sources into the back section like the original script

The __init__.py is working now and breaks up all the sources into individual sections ie. Author, book title, highlight type, page and location, section, subsection.