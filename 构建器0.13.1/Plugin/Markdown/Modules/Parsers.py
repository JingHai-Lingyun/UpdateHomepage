from typing import Union,List,Literal
from abc import abstractmethod,ABC
from Interfaces import encode_escape,Logger

logger = Logger('Markdown')
FIRSTLINE_SPACES = '    '

TAG_PARSER_MAPPING = {}

def handles(*args):
    def wrapper(cls):
        for name in args:
            TAG_PARSER_MAPPING[name] = cls
        return cls
    return wrapper

class Node():
    def __init__(self,tag,res,parent_stack):
        self.res = res
        self.name = None
        self.attrs = None
        self.tag = tag
        self.children = None
        self.parent_stack = parent_stack
        self.expose = False
        self.self_break = False
        self.parse_children()
    
    @property
    def ancestor(self) -> 'Node':
        if len(self.parent_stack) > 0:
            return self.parent_stack[-1]
        else:
            return None
    
    @property
    def inline(self) -> bool:
        raise NotImplementedError()
    
    @property
    def isblock(self) -> bool:
        return False
    
    @property
    def component_name(self) -> str:
        '''对应组件的名称'''
        return self.name
    
    @abstractmethod
    def get_replacement(self) -> Union[List|None]:
        '''获取替换框架占位符的字符串列表'''
    
    @abstractmethod
    def get_element_frame(self) -> str:
        '''获取元素框架'''

    @abstractmethod
    def parse_children(self) -> None:
        '''解析子元素'''
    
    @abstractmethod
    def add_child_node(self,child_node:'Node') -> None:
        '''增加子节点'''
    
    @abstractmethod
    def convert_children(self) -> str:
        '''获取子节点的xaml代码'''
    
    @abstractmethod
    def convert(self) -> str:
        '''获取本节点的xaml代码'''

class VoidNode(Node):
    def get_replacement(self):
        return None

    def get_element_frame(self):
        return ''
    
    def parse_children(self):
        pass
        
    def add_child_node(self,_):
        raise NotImplementedError()
    
    def convert_children(self):
        return ''

    def convert(self) -> str:
        return ''

class NodeBase(Node): 
    def __init__(self, tag, *args, **kwargs):
        super().__init__(tag, *args, **kwargs)
        self.name = tag.name
        self.attrs = tag.attrs
        self.parse_children()
    
    def get_replacement(self) -> Union[List|None]:
        return None

    def get_element_frame(self):
        components:dict[str,str] = self.res.components
        replace_list = self.get_replacement()
        replace_str = components.get(self.component_name)
        if replace_list:
            for k,v in replace_list:
                replace_str = replace_str.replace(f'${{{k}}}',encode_escape(str(v)))
        return replace_str
    
    def parse_children(self):
        if self.tag.contents:
            self.children = []
            for child in self.tag.contents:
                self.add_child_node(create_node(child,self.res,self.parent_stack + [self]))
                
    def add_child_node(self,child_node:Node):
        if child_node.expose:
            self.self_break = True
        self.children.append(child_node)
    
    def convert_children(self):
        content = ''
        for child in self.children:
            content += child.convert()
        return content
    
    def convert(self):
        content = self.convert_children() if self.children else ''
        if self.self_break:
            return content
        element_frame:str = self.get_element_frame()
        return element_frame.replace('${content}',content)

@handles('em','strong','code','del') 
class InlineNode(NodeBase):
    @property
    def inline(self):
        return True

@handles('ul')    
class LineNode(NodeBase):
    @property
    def inline(self):
        return False
    
class BlockNode(LineNode):
    @property
    def isblock(self):
        return True

class Text(VoidNode):
    def __init__(self,tag,*args,**kwargs):
        super().__init__(tag,*args,**kwargs)
        self.content = str(tag)
    
    @property
    def inline(self) -> Literal[True]:
        return True
    
    def convert(self):
        return encode_escape(self.content)

    def isempty(self):
        return len(self.content) == 0

    def __eq__(self,cmp):
        return cmp == self.content

@handles('li')
class MarkdownListItem(LineNode):
    def convert_children(self):
        content = ''
        in_paragraph = False
        for child in self.children:
            if child.inline:
                if child == '\n':
                    continue
                if not in_paragraph:
                    content += '<Paragraph>'
                    in_paragraph = True
            else:
                if in_paragraph:
                    content += '</Paragraph>'
                    in_paragraph = False
            content += child.convert()
        if in_paragraph:
            content += '</Paragraph>'
        return content

@handles('blockquote')
class Quote(LineNode):
    def convert_children(self):
        content = ''
        for child in self.children:
            if child.name != 'p':
                continue
            for grand_child in child.children:
                content += grand_child.convert()
        return content

@handles('p')           
class Paragraph(LineNode):
    
    def __init__(self, tag, *args, **kwargs):
        super().__init__(tag, *args, **kwargs)
        self.self_break = True
    
    def convert_children(self):                
        inblock = True
        content = FIRSTLINE_SPACES
        for child in self.children:
            if child.isblock:
                if not inblock:
                    inblock = True
                    content += '</Paragraph>'  
            else:
                if inblock:
                    inblock = False
                    content += '<Paragraph>'
            content += child.convert()
        if not inblock:
            content += '</Paragraph>'
        return content

@handles('h1','h2','h3','h4','h5')
class Heading(LineNode):
    @property
    def component_name(self) -> str:
        return 'heading'
        
    def get_replacement(self) -> Union[List|None]:
        return[('level',self.name[1:])]

@handles('a')
class Link(InlineNode):   
    def get_replacement(self) -> Union[List|None]:
        reps = [('link',self.attrs['href'])]
        ancestor = self.ancestor
        if ancestor.name == 'li':
            reps.append(('pos_down',9))
        else:
            reps.append(('pos_down',2))
        return reps

@handles('img')
class MarkdownImage(BlockNode):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.title = self.attrs.get('title')
        
    @property
    def component_name(self) -> str:
        return 'titled-img' if self.title else 'img'
    
    def get_replacement(self) -> Union[List|None]:
        replace_list = []
        replace_list.append(('source',self.attrs['src']))
        if self.title:
            replace_list.append(('title',self.title))
        return replace_list

def create_node(tag,res,parent_stack):
    if isinstance(tag,str):
        return Text(tag,res,parent_stack)
    else:
        return TAG_PARSER_MAPPING[tag.name](tag=tag,res=res,parent_stack=parent_stack)