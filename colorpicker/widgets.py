from django.forms.widgets import TextInput


class ColorPicker(TextInput):
    class Media:
        js = ('/static/jscolor.min.js',)
    
    def render(self, name, value, attrs=None):
        if 'class' not in attrs:
            attrs['class'] = ''
        else:
            attrs['class'] += ' '
        attrs['class'] += 'jscolor'
        return super(ColorPicker, self).render(name, value, attrs)
