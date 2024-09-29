import re
import markdown
from bs4 import BeautifulSoup
from Interfaces import script,encode_escape,Logger
from Parsers import create_node

def html2xaml(html,res):
    '''html转为xaml代码'''
    soup = BeautifulSoup(html,'html.parser')
    xaml = ''
    for tag in soup.find_all(recursive=False):
        xaml += create_node(tag,res,[]).convert()
    return xaml

del_pattern = re.compile(r'~~(.*)~~')

def md_del_replace(md:str):
    '''转译删除线'''
    return re.sub(del_pattern,r'<del>\1</del>',md)

def convert(card,res):
    '''生成xaml代码'''
    md = card['markdown']
    md = md_del_replace(md)
    html = markdown.markdown(md)
    xaml = html2xaml(html,res)
    return xaml

@script('MarkdownPresenter')
def script(card,res,**_):
    '''从markdown生成xaml代码脚本'''
    return convert(card,res)
