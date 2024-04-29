from datetime import datetime
import re
from collections import namedtuple

from bs4 import BeautifulSoup

from anki.notes import Note
from aqt import mw
from aqt.utils import getFile, showInfo, showText
from aqt.qt import QAction


def main():
    action = QAction('Import Kindle highlights...', mw)
    action.triggered.connect(import_highlights)
    mw.form.menuTools.addAction(action)


def import_highlights():
    #path = getFile(mw, 'Open Kindle clippings', cb=None, filter='Clippings file (*.txt *.html)', key='KindleHighlights')
    
    # No longer take txt, only html 
    path = getFile(mw, 'Open Kindle clippings', cb=None, filter='Clippings file (*.html)', key='KindleHighlights')
    with open(path, encoding='utf-8') as file:
        lower_path = path.lower()
        if lower_path.endswith('txt'): #TODO: remove
            clippings, bad_clippings = parse_text_clippings(file)
        elif lower_path.endswith('html'):
            clippings, bad_clippings = parse_html_clippings(file)
        else:
            raise RuntimeError(f'Unknown extension in path: {path!r}')
    # TODO: fix error which occurs when user "cancels" out of dialog box

    if bad_clippings:
        showText(
            f'The following {len(bad_clippings)} clippings could not be parsed:\n\n' +
            '\n==========\n'.join(bad_clippings))
    
    config = mw.addonManager.getConfig(__name__)

    highlight_clippings = list(highlights_only(clippings))
    clippings_to_add = after_last_added(highlight_clippings, last_added_datetime(config))

    model = mw.col.models.byName(config['model_name'])

    if not model:
        showInfo("Kindle import note type not found, please create the needed note type: \n" + config['model_name']
        + '\nThe fields needed are: ' + config['content_field'] + ', ' + config['source_field'] + ', ' 
        + config['authors_field'] + ', ' + config['title_field'] + ', ' + config['highlight_field'] + ', '
        + config['page_location_field'] + ', ' + config['section'] + ', ' + config['subsection'] + '.')
        
        raise ValueError('Could not find required notetype to import notes to: ' + config['model_name'] 
        + ' with the following fields: ' + config['content_field'] + ', ' + config['source_field'] + ', ' 
        + config['authors_field'] + ', ' + config['title_field'] + ', ' + config['highlight_field'] + ', '
        + config['page_location_field'] + ', ' + config['section'] + ', ' + config['subsection'] + '.')
        
        # TODO: create model(mw)

    last_added = None

    for clipping in clippings_to_add:
        note = Note(mw.col, model)
        note.fields = list(fields(clipping, model, config))
        mw.col.addNote(note)

        if clipping.added:
            last_added = clipping.added

    if last_added:
        config['last_added'] = parse_clipping_added(last_added).isoformat()
        mw.addonManager.writeConfig(__name__, config)

    def info():
        if clippings_to_add:
            yield f'{len(clippings_to_add)} new highlights imported'

        num_old_highlights = len(highlight_clippings) - len(clippings_to_add)
        if num_old_highlights:
            yield f'{num_old_highlights} old highlights ignored'

        num_not_highlights = len(clippings) - len(highlight_clippings)
        if num_not_highlights:
            yield f'{num_not_highlights} non-highlight clippings ignored'

    info_strings = list(info())
    if info_strings:
        showInfo(', '.join(info_strings) + '.')
    elif bad_clippings:
        showInfo('No other clippings found.')
    else:
        showInfo('No clippings found.')

# document => Atomic Habits: An Easy & Proven Way to Build Good Habits & Break Bad Ones
# authors => Clear, James 
# section => THE 4TH LAW: Make It Satisfying, 16: How to Stick with Good Habits Every Day
# subsection => ???
Clipping = namedtuple('Clipping', ('kind', 'document', 'page', 'location', 'added', 'content', 'authors', 'section', 'subsection'))

def parse_text_clippings(file):
    clippings = []
    bad_clippings = []

    current_clipping_lines = []
    for line in file:
        if line != '==========\n':
            current_clipping_lines.append(line)
            continue

        string = ''.join(current_clipping_lines)
        current_clipping_lines.clear()

        clipping = parse_text_clipping(string)

        if clipping:
            clippings.append(clipping)
        else:
            bad_clippings.append(string)

    if current_clipping_lines:
        bad_clippings.append(''.join(current_clipping_lines))

    return clippings, bad_clippings


def parse_text_clipping(string):
    match = re.fullmatch(CLIPPING_PATTERN, string)
    if not match:
        return None
    # TODO: this will break because missing new args to namedtuple Clipping constructor
    return Clipping(**match.groupdict())


CLIPPING_PATTERN = r'''\ufeff?(?P<document>.*)
- Your (?P<kind>.*) on (?:page (?P<page>.*) \| )?(?:Location (?P<location>.*) \| )?Added on (?P<added>.*)

(?P<content>.*)
?'''


def parse_html_clippings(file):
    clippings = []
    bad_clippings = []

    soup = BeautifulSoup(file, 'html.parser')

    title = None
    authors = None
    section = None
    kind = None
    subsection = None
    page = None
    location = None

    for paragraph in soup.find_all(class_=True):
        classes = paragraph['class']
        text = paragraph.get_text().strip()

        if 'bookTitle' in classes:
            title = text

        if  'authors' in classes:
            authors = text

        if 'sectionHeading' in classes:
            section = text

        if 'noteHeading' in classes:
            match = re.fullmatch(NOTE_HEADING_PATTERN, text)
            if not match:
                bad_clippings.append(text)
                kind = None
                location = None
                page = None
                subsection = None
            else:
                kind = match['kind'].strip()
                location = match['location'].strip()
                page = match['page'].strip() if match['page'] else None
                if match['subsection']:
                    subsection = match['subsection'].strip()
                else:
                    subsection = None

        if 'noteText' in classes:
            content = text
        else:
            continue

        if not kind or not location:
            bad_clippings.append(text)
            continue

        if title:
            document = title
        # NICK: below removed and split into own params in Clipping
        # if title and authors:
        #     document = f'{title} ({authors})'
        # elif title:
        #     document = title
        # elif authors:
        #     document = authors

        # if section:
        #     document += ' ' + section + ','

        # if subsection:
        #     document += ' ' + subsection + ','

        clippings.append(Clipping(
            kind=kind,
            document=document,
            page=page,
            location=location,
            added=None,
            content=content,
            authors=authors if authors else '',
            section=section if section else '',
            subsection=subsection if subsection else '',
        ))
    return clippings, bad_clippings

# example html 1:    
#  Highlight(<span class="highlight_yellow">yellow</span>) - 13: How to Stop Procrastinating by Using the Two-Minute Rule > Page 164 · Location 1959
# example html 2:
#  Highlight(<span class="highlight_yellow">yellow</span>) - Location 273

NOTE_HEADING_PATTERN = r'(?P<kind>.*?)\s*-\s*(?:(?P<subsection>.*)\s*>\s*)?(Page\s*(?P<page>.*)?\s· )?Location\s*(?P<location>.*)'

def after_last_added(clippings, last_added):
    if not last_added:
        return clippings

    def reversed_clippings_after_last_added():
        for clipping in reversed(clippings):
            if clipping.added:
                clipping_added = parse_clipping_added(clipping.added)
                if clipping_added and clipping_added <= last_added:
                    return
            yield clipping

    clippings_after_last_added = list(reversed_clippings_after_last_added())
    clippings_after_last_added.reverse()
    return clippings_after_last_added


def parse_clipping_added(clipping_added):
    return datetime.strptime(clipping_added, '%A, %B %d, %Y %I:%M:%S %p')


def last_added_datetime(config):
    last_added_config = config['last_added']
    return datetime.strptime(last_added_config, '%Y-%m-%dT%H:%M:%S') if last_added_config else None

# only include if type is "highlights"
def highlights_only(clippings):
    for clipping in clippings:
        if 'highlight' in clipping.kind.lower():
            yield clipping


def fields(clipping, model, config):
    content_yielded = False
    source_yielded = True

    # example
    # clipping.kind => Kindle [[highlight(yellow) kind]] from 
    # clipping.document => Atomic Habits: An Easy & Proven Way to Build Good Habits & Break Bad Ones (Clear, James) THE 4TH LAW: Make It Satisfying, 16: How to Stick with Good Habits Every Day
    # clipping.page => page 201
    # clipping.location => location 2380
    for field in mw.col.models.fieldNames(model):
        if field == config['content_field']:
            yield clipping.content.strip()
            content_yielded = True
        elif field == config['source_field']: # if model has the source_field in the config, which right now is "Extra" and is unsued/doesn't exist
            # yield 'Kindle {kind} from {document}{page}{location}{added}'.format(
            #     kind=clipping.kind.lower(),
            #     document=clipping.document,
            #     page=' page ' + clipping.page if clipping.page is not None else '',
            #     location=' location ' + clipping.location if clipping.location is not None else '',
            #     added=' added ' + clipping.added if clipping.added is not None else '',
            # )
            yield ''
            # TODO: figure out what to do about source_yielded
            source_yielded = True
        elif field == config["authors_field"]:
            yield clipping.authors.strip()
        elif field == config["title_field"]:
            yield clipping.document.strip()
        elif field == config["highlight_field"]: # type of hightlight (yellow/red/etc)
            # yield clipping.kind.lower() #TODO: type of 
            yield re.findall(r'highlight\((.*)\)', clipping.kind.lower()).pop()
        elif field == config["page_location_field"]:
            yield '{page}{location}'.format(
                page=' page ' + clipping.page if clipping.page is not None else '',
                location=' location ' + clipping.location if clipping.location is not None else '',
            )
        elif field == config["section"]:
            yield clipping.section.strip()
        elif field == config["subsection"]:
            yield clipping.subsection.strip()
        else:
            yield ''
    if not (content_yielded):
        raise ValueError('Could not find content fields in model.')

    if not (source_yielded):
       raise ValueError('Could not find source fields in model.')


main()
