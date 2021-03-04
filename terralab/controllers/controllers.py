# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging
import sys
import traceback

logger = logging.getLogger(__name__)

class Terralab(http.Controller):
    @http.route('/terralab/customview/', auth='public')
    def customview(self, **kw):
        return "Custom view..."
