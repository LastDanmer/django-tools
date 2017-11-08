# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.core.paginator import Page
from django.core.paginator import Paginator
from django.utils import six

"""
Template example:
{% if paginator.num_pages > 1 %}
    <ul class="pagination offset-top-20">
        {% if page_obj.has_previous %}
            <li><a href="{% page_url base_url page_obj.previous_page_number %}">Prev</a></li>
        {% endif %}

        {% if page_obj.show_first %}
            <li><a href="{% page_url base_url 1 %}">1</a></li>

            {% if page_obj.show_first_ellipsis %}
                <li><span>...</span></li>
            {% endif %}
        {% endif %}

        {% for page_num in page_obj.relative_range %}
            <li{% if page_num == page_obj.number %} class="active"{% endif %}>
                <a href="{% page_url base_url page_num %}">{{ page_num }}</a>
            </li>
        {% endfor %}

        {% if page_obj.show_last %}
            {% if page_obj.show_last_ellipsis %}
                <li><span>...</span></li>
            {% endif %}

            <li><a href="{% page_url base_url paginator.num_pages %}">{{ paginator.num_pages }}</a></li>
        {% endif %}

        {% if page_obj.has_next %}
            <li><a href="{% page_url base_url page_obj.next_page_number %}">Next</a></li>
        {% endif %}
    </ul>
{% endif %}
"""


class EllipsisPaginator(Paginator):
    max_range = 5
    at_one_side = 0

    def __init__(self, *args, **kwargs):
        if 'max_range' in kwargs:
            self.max_range = kwargs.pop('max_range')
        self.at_one_side = self.max_range // 2
        super(EllipsisPaginator, self).__init__(*args, **kwargs)

    def _get_page(self, *args, **kwargs):
        return EllipsisPage(*args, **kwargs)


class EllipsisPage(Page):
    is_calculated = False
    start_page = None
    end_page = None

    def __init__(self, *args, **kwargs):
        super(EllipsisPage, self).__init__(*args, **kwargs)
        self._calculate()

    def _calculate(self):
        offset = 0

        self.start_page = self.number - self.paginator.at_one_side
        # correcting start page to be more than 0
        if self.start_page < 1:
            offset = 1 - self.start_page
            self.start_page = 1

        # displaying start page to near to real start page
        # don't need to have +1 page in page range (because self.show_first will be true)
        elif self.start_page == 2:
            self.start_page = 1
            offset -= 1

        self.end_page = self.number + self.paginator.at_one_side + offset
        # correcting end page to be not more than we have
        if self.end_page > self.paginator.num_pages:
            offset = self.end_page - self.paginator.num_pages
            self.end_page -= offset
            # and after that again start page:
            self.start_page -= offset
            if self.start_page < 1:
                self.start_page = 1

        # displaying end page to near to real end page
        # don't need to have +1 page in page range (because self.show_last will be true)
        elif self.end_page == (self.paginator.num_pages - 1):
            self.end_page = self.paginator.num_pages
            self.start_page += 1

    def relative_range(self):
        return six.moves.range(self.start_page, (self.end_page + 1))

    def show_first(self):
        return self.start_page != 1

    def show_first_ellipsis(self):
        return self.start_page > 2

    def show_last(self):
        return self.end_page != self.paginator.num_pages

    def show_last_ellipsis(self):
        return (self.paginator.num_pages - self.end_page) > 1
