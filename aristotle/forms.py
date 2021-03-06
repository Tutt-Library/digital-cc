from flask_wtf import FlaskForm as Form
from wtforms import BooleanField, SelectField, StringField, FormField, FieldList

SEARCH_TYPES = (
    ("kw", "Keyword"),
    ("creator", "Creator"),
    ("title", "Title"),
    ("subject", "Subject"),
    ("number", "Number")
)
    
class SimpleSearch(Form):
    mode = SelectField("Mode",
        choices=SEARCH_TYPES)
    q = StringField("Search")


class ObjectFormatForm(Form):
    audio = BooleanField("Audio")
    image = BooleanField("Image")
    mixed_material = BooleanField("Mixed Material")
    moving_image = BooleanField("Moving Image")
    pdf = BooleanField("PDF")

class OperatorSearch(SimpleSearch):
    operator = SelectField("operator", choices=[("and", "AND"), 
                                                ("or", "OR"), 
                                                ("not","NOT")])
    
class AdvancedSearch(Form):
    text_search = FieldList(FormField(OperatorSearch), min_entries=2)
    by_collection = SelectField("Narrow by Collection",
        choices=(("none", "None"),
                 ("thesis", "Thesis"),
                 ("special collections", "Special Collections"),
                 ("general", "General College"),
                 ("music library", "Music Library")))
    by_genre = SelectField("Narrow by Genre")
    by_topic = SelectField("Narrow by Topic")
##    by_thesis_dept = SelectField("Narrow by Thesis Department")
##    by_thesis_advisor = StringField("Narrow by Thesis Advisor")
    obj_format = FormField(ObjectFormatForm)

