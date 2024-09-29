from .IO import File
from .styles import get_style_code
from .utils import PropertySetter
from .utils.event import triggers
from .utils.formatter import format_code
from .library import Library
from .logger import Logger
from .i18n import locale as t
from .config import config

logger = Logger('Page')

class PageBase():
    "页面基类"
    def __init__(self, project) -> None:
        self.project = project
    
    def generate(self, *args, **kwargs):
        "获取页面 XAML 代码"
    
    @property
    def display_name(self):
        raise NotImplementedError()
    
    def get_content_type(self, setter):
        return 'application/xml'

class FileBasedPage(PageBase):
    "基于文件的页面，仅应用于继承"
    def __init__(self, file:File, project) -> None:
        super().__init__(project)
        self.file = file
    
    def generate(self, *args, **kwargs):
        raise NotImplementedError()
        
class RawXamlPage(FileBasedPage):
    
    @property
    def display_name(self):
        return self.file.name
    
    def generate(self, *args, **kwargs):
        return self.file.data

class CardStackPage(FileBasedPage):
    def __init__(self, file:File, project) -> None:
        super().__init__(file, project)
        data = file.data
        self.setter = PropertySetter(data.get('fill'), data.get('override'))
        self.name = data.get('name', file.name)
        self.display_name_str = data.get('display_name', self.name)
        self.cardrefs = data.get('cards',{})
        self.alias = data.get('alias', [])
    
    @property
    def display_name(self):
        return self.display_name_str
    
    @triggers('page.generate')
    def generate(self, *args, **kwargs):
        xaml = self.getframe()
        xaml = xaml.replace('${animations}', '')  # TODO
        xaml = xaml.replace('${styles}', get_style_code(self.project.resources.styles))
        xaml = xaml.replace('${content}', self.generate_content(*args, **kwargs))
        return xaml

    def generate_content(self, *args, **kwargs):
        "生成页面主要内容"
        runtime_setter = self.setter.clone()
        runtime_setter.attach(kwargs.get('setter'))
        content = ''
        for card_ref in self.cardrefs:
            content += self.__getcardscontent(card_ref, setter = runtime_setter)
        return content

    def __getcardscontent(self, ref, setter:PropertySetter):
        "一行可能有多个卡片，本方法处理整行"
        ref = format_code(code=ref, card=setter.toProperties(), project=self.project)
        code = ''
        for each_card_ref in ref.split(';'):
            code += self.__getonecardcontent(each_card_ref, setter.clone())
        return code
    
    def __getonecardcontent(self, ref, setter:PropertySetter):
        "一行可能有多个卡片，本方法处理单个卡片"
        ref = ref.replace(' ', '').split('|')
        real_ref = ref[0]
        args = ref[1:] if len(ref) > 1 else []
        if real_ref  == '':
            logger.info(t('project.get_card.null'))
            return ''
        setter.attach(PropertySetter.fromargs(args))
        logger.info(t('project.get_card', card_ref=real_ref))
        card = self.__getcard(real_ref,setter)
        if not card:
            return ''
        return self.project.template_manager.build(card)
    
    def __getcard(self,ref,setter):
        if config('Debug.Enable'):
            return self.__getcardunsafe(ref, setter)
        try:
            return self.__getcardunsafe(ref, setter)
        except Exception as ex:
            logger.warning(t('project.get_card.failed', ex=ex))
            return None 
    
    def __getcardunsafe(self,ref,setter):
        card = self.project.base_library.get_card(ref, False)
        card = setter.decorate(card)
        return card
    
    def getframe(self):
        return self.project.resources.page_templates['Default']