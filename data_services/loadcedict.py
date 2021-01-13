from pymongo import MongoClient
from pypinyin import pinyin as pfmt
from pypinyin import Style
import pandas as pd
from config import *


def init_mongodb():
    """
    Connects to mongoDB, creates indices, and returns collection for CEDICT load
    """
    client = MongoClient(DB_URI)
    db = client[DB_NAME]
    colls = {
        'cedict': db[CEDICT_COLL_NAME],
        'user': db[USER_COLL_NAME],
        'user_docs': db[USER_DOC_COLL_NAME],
        'user_vocab': db[USER_VOCAB_COLL_NAME],
        'user_vocab_list': db[USER_VOCAB_LIST_COLL_NAME]
    }
    # CEDICT Indices
    colls['cedict'].create_index([ ("simp", 1) ])
    colls['cedict'].create_index([ ("trad", 1) ])
    colls['cedict'].create_index([ ("simp", 1), ("raw_pinyin", -1) ], unique=True)
    colls['cedict'].create_index([ ("trad", 1), ("raw_pinyin", -1) ])
    # User Indices
    colls['user'].create_index([ ("username", 1)], unique=True)
    colls['user'].create_index([ ("email", 1)], unique=True)
    colls['user'].create_index([ ("username", 1), ("email", 1)], unique=True)
    # User Doc Indices
    colls['user_docs'].create_index([ ("username", 1)])
    colls['user_docs'].create_index([ ("username", 1), ("title", 1)], unique=True)
    # User Vocab Indices
    colls['user_vocab'].create_index([ ("username", 1)])
    colls['user_vocab'].create_index([ ("username", 1), ("cn_type", 1)])
    colls['user_vocab'].create_index([ ("username", 1), ("phrase.simp", 1)])
    colls['user_vocab'].create_index([ ("username", 1), ("phrase.trad", 1)])
    colls['user_vocab'].create_index([ ("username", 1), ("phrase.simp", 1), ("phrase.raw_pinyin", -1)], unique=True)
    colls['user_vocab'].create_index([ ("username", 1), ("phrase.trad", 1), ("phrase.raw_pinyin", -1)], unique=True)
    # User Vocab List Index
    colls['user_vocab_list'].create_index([ ("username", 1) ], unique=True)
    return colls['cedict']

def convert_digits_to_chars(s):
    """
    Formats edge-case characters from pypinyin (pfmt) library
    """
    repl_dict = {
        '1': '一',
        '2': '二',
        '3': '三',
        '4': '四',
        '5': '五',
        '6': '六',
        '7': '七',
        '8': '八',
        '9': '九',
        '0': '零',
        '%': '啪', # FYI: same pinyin, not actually the same word
    }
    for k, v in repl_dict.items():
        s = s.replace(k, v)
    return s

def format_defn_html(defn_in):
    """ 
    Takes delimited definition and generates corresponding HTML.

    Multiple definitions must be delimited by the '$' character (used bc it isn't in CEDICT)

    Input: "/The first definition/The second definition/$/Alternate first definition/Alternate second definition..."
    Output: "1. The first definition<br>2. The second definition<hr>1. Alternate first definition<br>2. Alternate second definition..."
    """
    res = ''
    split_defn = defn_in.split('$')
    for i, defn in enumerate(split_defn):
        clean_defn = defn.replace('\"', '\'') # some entries in CEDICT use " character
        defns = clean_defn.split('/')[1:-1] # removes first and last splits, which are '' in this case
        for j, d in enumerate(defns):
            if j != len(defns) - 1:
                res += f'{j+1}. {d}<br>'
            elif i != len(split_defn) - 1 :
                res += f'{j+1}. {d}<hr>'
            else:
                res += f'{j+1}. {d}'
    return res

def render_phrase_table_html(phrase, raw_pinyin, formatted_pinyin, defn, zhuyin):
    """ 
    Takes CEDICT entry information and generates corresponding HTML
    """
    download_icon_loc = 'https://icons.getbootstrap.com/icons/download.svg'
    sound_icon_loc = 'https://icons.getbootstrap.com/icons/volume-up-fill.svg'

    def get_phrase_data_as_lists():
        # get individual words (used in pinyin name)
        word_list = [w for w in phrase]
        pinyin_list = formatted_pinyin.split(' ')
        zhuyin_list = zhuyin.split(' ')
        # handle case for non-chinese character pinyin getting "stuck" (e.g. ['AA'] should be ['A', 'A'])
        if len(word_list) > len(pinyin_list):
            # from inspection, this is always first or last item. Hard-code for edge cases (['dǎ', 'call'], ['mǔ', 'tāi', 'solo'], ['kǎ', 'lā', 'OK'])
            split_first_non_chinese_phrase = lambda pylist: [c for c in pylist[0]] + pylist[1:]
            split_last_non_chinese_phrase = lambda pylist: pylist[:-1] + [c for c in pylist[-1]]
            if pinyin_list[0] not in {'dǎ', 'mǔ', 'kǎ'} and len(pinyin_list[0]) > 1:
                pinyin_list = split_first_non_chinese_phrase(pinyin_list)
                zhuyin_list = split_first_non_chinese_phrase(zhuyin_list)
            elif len(pinyin_list[-1]) > 1:
                pinyin_list = split_last_non_chinese_phrase(pinyin_list)
                zhuyin_list = split_last_non_chinese_phrase(zhuyin_list)
        # print(f"word_list  : {word_list}\npinyin_list: {pinyin_list}\nzhuyin_list: {zhuyin_list}")
        assert len(word_list) == len(pinyin_list)
        assert len(word_list) == len(zhuyin_list)
        return word_list, pinyin_list, zhuyin_list

    def perform_render(use_pinyin):
        # generate html
        word_list, pinyin_list, zhuyin_list = get_phrase_data_as_lists()
        n_words = len(word_list)
        res = ''
        phonetics = raw_pinyin if use_pinyin else zhuyin
        span_start = f'<span tabindex="0" data-bs-toggle="popover" data-bs-trigger="focus" data-bs-content="{format_defn_html(defn)}" \
            title="{phrase} [{phonetics}] \
            <a role=&quot;button&quot; href=&quot;#~{phrase}&quot;><img src=&quot;{sound_icon_loc}&quot;></img></a> \
            <a role=&quot;button&quot; href=&quot;#{phrase}&quot;><img src=&quot;{download_icon_loc}&quot;></img></a>" \
            data-bs-html="true">' # ... dear neptune...
        res += span_start.replace('            ', '')
        res += '<table style="display: inline-table; text-align: center;">'
        if use_pinyin:
            pinyin_html = ''.join([f'<td style="visibility: visible" class="pinyin" name="{word_list[i]}">{pinyin_list[i]}</td>' for i in range(n_words)])
            pinyin_html = f'<tr>{pinyin_html}</tr>'
            res += pinyin_html
        else:
            zhuyin_html = ''.join([f'<td style="visibility: visible" class="zhuyin" name="{word_list[i]}">{zhuyin_list[i]}</td>' for i in range(n_words)])
            zhuyin_html = f'<tr>{zhuyin_html}</tr>'
            res += zhuyin_html
        phrase_html = ''.join([f'<td class="phrase">{w}</td>' for w in phrase])
        phrase_html = f'<tr>{phrase_html}</tr>'
        res += phrase_html
        res += '</table>'
        res += '</span>'
        return res
        
    res_pinyin = perform_render(use_pinyin=True)
    res_zhuyin = perform_render(use_pinyin=False)
    return (res_pinyin, res_zhuyin)

def load_cedict(coll):
    """
    Performs the CEDICT load into the specified collection
    """
    if coll.estimated_document_count() > 100000:
        print('CEDICT is already loaded -- skipping operation...')
        return

    SORTED_CEDICT_CSV_PATH = 'static/sorted_cedict_ts.csv'
    print(f'Loading CEDICT from {SORTED_CEDICT_CSV_PATH} - this takes a few seconds...')
    cedict_df = pd.read_csv(SORTED_CEDICT_CSV_PATH, index_col=0)
    entry_list = []
    prev_trad, prev_simp, prev_raw_pinyin = None, None, None # Track lines with identical pinyin + phrase
    for _, row in cedict_df.iterrows():
        trad, simp, raw_pinyin, defn = row

        # skip cases where definition is a "variant of" another CEDICT entry
        if "variant of" in defn:
            continue

        # get formatted pinyin
        flatten_list = lambda l: [i for j in l for i in j] # [[a], [b], [c]] => [a, b, c]
        formatted_simp = convert_digits_to_chars(simp)
        formatted_pinyin = ' '.join(flatten_list(pfmt(formatted_simp)))

        # get zhuyin (BOPOMOFO)
        zhuyin = ' '.join(flatten_list(pfmt(formatted_simp, style=Style.BOPOMOFO)))
        
        # handle case where lines can be merged (based on raw_pinyin)
        # NOTE: this does cause some data loss for traditional entries with matching simplified phrases, treating as negligible
        if (prev_raw_pinyin == raw_pinyin) and ((prev_simp == simp) or (prev_trad == trad)):
            last_entry = entry_list.pop()
            defn = last_entry['def'] + '$' + defn

        # render html
        trad_html, trad_zhuyin_html = render_phrase_table_html(trad, raw_pinyin, formatted_pinyin, defn, zhuyin)
        simp_html, simp_zhuyin_html = render_phrase_table_html(simp, raw_pinyin, formatted_pinyin, defn, zhuyin)

        # append entry
        entry_list.append({
            'trad': trad,
            'simp': simp,
            'raw_pinyin': raw_pinyin,
            'def': defn,
            'formatted_pinyin': formatted_pinyin,
            'trad_html': trad_html,
            'simp_html': simp_html,
            'zhuyin': zhuyin,
            'trad_zhuyin_html': trad_zhuyin_html,
            'simp_zhuyin_html': simp_zhuyin_html
        })
    
        # update prev items
        prev_trad, prev_simp, prev_raw_pinyin = trad, simp, raw_pinyin

    print('Loaded. Sending to db...')
    coll.insert_many(entry_list)
    return

if __name__ == '__main__':
    cedict_coll = init_mongodb()
    load_cedict(cedict_coll)