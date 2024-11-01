"""
Formatters to take exported database data and display in a variety of formats.
"""

from .baseformatter import BaseFormatter
from .textformatter import TextFormatter
from .htmlformatter import HtmlFormatter
from .nlpformatter import NlpFormatter


NAME_TO_FORMATTER = {}

for cls in list(locals().values()):
    if (
        isinstance(cls, type)
        and issubclass(cls, BaseFormatter)
        and cls != BaseFormatter
    ):
        NAME_TO_FORMATTER[cls.name()] = cls
