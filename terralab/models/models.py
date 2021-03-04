# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging
from googleapiclient.discovery import build
import google.oauth2.credentials
import re

logger = logging.getLogger(__name__)

def get_google_spreadsheets(access_token):
    credentials = google.oauth2.credentials.Credentials(access_token)
    service = build('sheets', 'v4', credentials=credentials)
    sheets = service.spreadsheets()
    return sheets

# Terralab models

class SampleType(models.Model):
    _name = 'terralab.sampletype'
    _description = 'TerraLab Sample Type'
    samples = fields.One2many('terralab.sample', 'sample_type', 'Samples') # There are many Samples of one SampleType
    test_types = fields.One2many('product.template', 'terralab_sample_type', 'Test Types') # There are many TestTypes of one SampleType (they are Products)
    name = fields.Char()

class Sample(models.Model):
    _name = 'terralab.sample'
    _description = 'TerraLab Sample'
    sample_type = fields.Many2one('terralab.sampletype', 'Sample Type') # Sample is of a specific SampleType
    tests = fields.One2many('terralab.test', 'sample', 'Tests') # Sample may have many Tests attached to it
    order = fields.Many2one('sale.order', 'Order') # Sample is always attached to an Order
    serial_number = fields.Char() # Freeform serial number to identity sample

    def name_get(self):
        return [(sample.id, '%s %s %s' % (sample.order.name, sample.sample_type.name if sample.sample_type else '(no sample type)', sample.serial_number if sample.serial_number else '(no serial number)')) for sample in self]

    # What's the next required action for this sample?
    def compute_terralab_next_action(self, order_terralab_status):
        if not self.sample_type:
            return _('Set sample type for sample %s') % (self.name_get()[0][1])
        if not self.serial_number:
            return _('Set serial number for sample %s') % (self.name_get()[0][1])
        if len(self.tests) <= 0:
            return _('Add tests for sample %s') % (self.name_get()[0][1])
        for test in self.tests:
            required_action = test.compute_terralab_next_action(order_terralab_status)
            if required_action:
                return required_action
        # No action required for this sample
        return ''

class TestVariableType(models.Model):
    _name = 'terralab.testvariabletype'
    _description = 'TerraLab Test Variable Type'
    test_type = fields.Many2one('product.template', 'Test Type') # Test Variable Types are attached to a specific TestType (Product)
    test_variables = fields.One2many('terralab.testvariable', 'test_variable_type', 'Test Variables') # There are many TestVariables of one TestVariableType
    name = fields.Char()
    spreadsheet_input_ref = fields.Char() # Spreadsheet input reference, Sheet!A1

class TestVariable(models.Model):
    _name = 'terralab.testvariable'
    _description = 'TerraLab Test Variable'
    sample = fields.Many2one('terralab.sample', 'Sample') # Every TestVariable is attached to a specific Sample
    test = fields.Many2one('terralab.test', 'Test') # Every TestVariable is attached to a specific Test
    test_variable_type = fields.Many2one('terralab.testvariabletype', 'Test Variable Type') # Every TestVariable has a specific TestVariableType
    value = fields.Char()
    name = fields.Char(compute='_get_name', store=True)
    order_name = fields.Char(compute='_get_order_name', store=True)

    @api.depends('test', 'test_variable_type', 'value')
    def _get_name(self):
        for item in self:
            if item.test and item.test_variable_type:
                # This is ugly, sorry.
                for test in item.test:
                    for test_id, test_name in test.name_get():
                        item.name = '%s %s' % (test_name, item.test_variable_type.name)
            else:
                item.name = ''

    @api.depends('sample', 'sample.order')
    def _get_order_name(self):
        for item in self:
            if item.sample and item.sample.order:
                item.order_name = item.sample.order.name
            else:
                item.order_name = ''

    # What's the next required action for this test variable?
    def compute_terralab_next_action(self, order_terralab_status):
        if order_terralab_status in ('submitted', 'accepted', 'rejected'):
            if self.value == '' or self.value == False:
                return _('Add value for test variable %s') % (self.name)
        # No action required for this test variable
        return ''

#    def write(self, values):
#        super(TestVariable, self).write(values)
#        # Recompute next action field for related order
#        order = self.sample.order
#        model = self.env['sale.order']
#        self.env.add_todo(model._fields['terralab_next_action'], order)
#        model.recompute()
#        return True

# Note: Test Types are actually products
class TestType(models.Model):
    _name = 'product.template'
    _inherit = 'product.template'
    terralab_test_variable_types = fields.One2many('terralab.testvariabletype', 'test_type', 'TerraLab TestVariable Types') # Test Types have a number of Test Variable Types, used to create Test Variables for Tests
    terralab_sample_type = fields.Many2one('terralab.sampletype', 'TerraLab Sample Type') # Test Types have a SampleType, so that a Test can be attached to Samples of that type
    terralab_spreadsheet = fields.Many2one('terralab.spreadsheet', 'TerraLab Spreadsheet') # Spreadsheet used to calculate test results
    terralab_test_name = fields.Char()
    terralab_spreadsheet_result_ref = fields.Char() # Spreadsheet result reference, Sheet!A1

class Spreadsheet(models.Model):
    _name = 'terralab.spreadsheet'
    _description = 'TerraLab Spreadsheet'
    name = fields.Char()
    spreadsheet_url = fields.Char()
    spreadsheet_id = fields.Char()
    test_types = fields.One2many('product.template', 'terralab_spreadsheet', 'Test Types')

    def write(self, values):
        new_url = values.get('spreadsheet_url', None)
        if new_url:
            # Extract spreadsheet ID
            m = re.match(r'.*/([^/]+)/edit.*', new_url)
            logger.info('Matches: %s' % (m))
            if m:
                values['spreadsheet_id'] = m.group(1)
        super(Spreadsheet, self).write(values)
        logger.info('Writing Spreadsheet %s' % (values))
        return True

    def calculate_result(self, test_type, test_variables):
        access_token = self.env['google.drive.config'].get_access_token(scope='https://spreadsheets.google.com/feeds')
        spreadsheets = get_google_spreadsheets(access_token)
        logger.info('Calculating spreadsheet %s test result with variables: %s' % (self.spreadsheet_id, test_variables))
        # Set input variables
        # XXX - Could we combine these to a single update() call?
        for test_variable in test_variables:
            logger.info('Setting input variable %s=%s' % (test_variable.test_variable_type.spreadsheet_input_ref, test_variable.value))
            update_result = spreadsheets.values().update(spreadsheetId=self.spreadsheet_id, range=test_variable.test_variable_type.spreadsheet_input_ref, valueInputOption='USER_ENTERED', body={'values':[[test_variable.value]]}).execute()
            logger.info('Update result: %s' % (update_result))
        # Retrieve result variable
        result = spreadsheets.values().get(spreadsheetId=self.spreadsheet_id, range=test_type.terralab_spreadsheet_result_ref).execute()
        values = result.get('values', [])
        logger.info('RESULT VALUES: %s' % (values))
        return values[0][0]

class Test(models.Model):
    _name = 'terralab.test'
    _description = 'TerraLab Test'
    test_type = fields.Many2one('product.template', 'Test Type') # A Test is of a specific Test Type
    sample = fields.Many2one('terralab.sample', 'Sample') # A Test is attached to a specific Sample
    test_variables = fields.One2many('terralab.testvariable', 'test', 'Test Variables') # A Test has a number of Test Variables
    test_result = fields.Char()

    def name_get(self):
        return [(test.id, '%s %s %s %s' % (test.sample.order.name, test.sample.sample_type.name, test.sample.serial_number, test.test_type.name)) for test in self]

    # Order form action: Calculate test results
    def action_terralab_calculate(self):
        # self.ensure_one()
        self.calculate_test_result()
        return None
        #next_action = self.env.ref('terralab.calculated_orders_list_action').read()[0]
        #next_action['target'] = 'main'
        #return next_action

    # What's the next required action for this test?
    def compute_terralab_next_action(self, order_terralab_status):
        if order_terralab_status in ('draft', 'submitted'):
            # In draft or submitted state test variables not yet needed; must accept first
            return ''
        if len(self.test_variables) <= 0:
            return _('Add test variables for test %s') % (self.name_get()[0][1])
        for test_variable in self.test_variables:
            required_action = test_variable.compute_terralab_next_action(order_terralab_status)
            if required_action:
                return required_action
        # No action required for this test
        return ''

    # Calculate test result
    def calculate_test_result(self):
        spreadsheet = self.test_type.terralab_spreadsheet
        result = spreadsheet.calculate_result(self.test_type, self.test_variables)
        self.write({
            'test_result': result,
        })

# Extend Odoo Order
class Order(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'
    terralab_status = fields.Selection([
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('accepted', _('Accepted')),
        ('rejected', _('Rejected')),
        ('calculated', _('Calculated')),
        ('report_generated', _('Report Generated')),
        ('completed', _('Completed')),
    ], string='TerraLab Status', default=None)
    terralab_samples = fields.One2many('terralab.sample', 'order', 'TerraLab Samples') # All Samples attached to this Order
    terralab_reports = fields.One2many('terralab.report', 'order', 'TerraLab Reports') # All Reports attached to this Order
    terralab_next_action = fields.Char(compute='_get_terralab_next_action', store=True) # Next action required

    @api.depends('terralab_samples', 'terralab_status', 'terralab_samples.tests', 'terralab_samples.tests.test_variables', 'terralab_samples.tests.test_variables.value')
    def _get_terralab_next_action(self):
        for item in self:
            item.terralab_next_action = item.compute_terralab_next_action(self.terralab_status)

    def compute_terralab_next_action(self, order_terralab_status):
            if len(self.terralab_samples) <= 0:
                return _('Add at least one sample')
            for sample in self.terralab_samples:
                required_action = sample.compute_terralab_next_action(order_terralab_status)
                if required_action:
                    return required_action
            # No required action found; check status
            if self.terralab_status == 'draft':
                # Order should be submitted
                return _('Submit order')
            elif self.terralab_status == 'submitted':
                # Order should be accepted
                return _('Accept or reject order')
            elif self.terralab_status == 'accepted':
                # Order should be calculated
                return _('Calculate test results')
            elif self.terralab_status == 'calculated':
                # Report should be generated
                return _('Generate report')
            elif self.terralab_status == 'report_generated':
                # Order should be completed
                return _('Complete order')
            return ''

    @api.model
    def create(self, values):
        Product = self.env['product.template']
        OrderLine = self.env['sale.order.line']
        TestVariable = self.env['terralab.testvariable']
        # If any TerraLab Samples are included in the order, set the TerraLab status to Draft so it appears in lists
        if len(values.get('terralab_samples', [])) > 0:
            logger.info('Created Order contains TerraLab Samples, setting status to draft')
            values['terralab_status'] = 'draft'
        order = super(Order, self).create(values)
        logger.info('Creating Order %s' % (values))
        # Create Order Lines for all Tests
        for sample in order.terralab_samples:
            logger.info('Checking Order Sample %s' % (sample))
            for test in sample.tests:
                # Find TestType of test
                logger.info('Checking Order Sample Test %s' % (test))
                test_type = Product.browse(test.test_type.id)
                logger.info('Test Type: %s' % (test_type))
                # Create Order Line for this Test
                logger.info('Creating Order Line for Order %s Test %s' % (order.id, test))
                order_line = OrderLine.create({
                    'order_id': order.id,
                    'product_id': test_type.id,
                    'name': test_type.name,
                    'product_uom': test_type.uom_id.id,
                })
                order_line.product_id_change()
                # Create Test Variables for this Test
                for test_variable_type in test_type.terralab_test_variable_types:
                    logger.info('Creating Test Variable for Test Variable Type: %s' % (test_variable_type))
                    TestVariable.create({
                        'test_variable_type': test_variable_type.id,
                        'sample': sample['id'],
                        'test': test['id'],
                    })
        return order

    def write(self, values):
        super(Order, self).write(values)
        logger.info('Writing Order %s' % (values))
        return True

    # Order form action: Mark order TerraLab status as submitted
    def action_terralab_submit(self):
        # self.ensure_one()
        self.write({
            'terralab_status': 'submitted',
        })
        next_action = self.env.ref('terralab.submitted_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: Mark order TerraLab status as draft
    def action_terralab_draft(self):
        # self.ensure_one()
        self.write({
            'terralab_status': 'draft',
        })
        next_action = self.env.ref('terralab.draft_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: Mark order TerraLab status as accepted
    def action_terralab_accept(self):
        # self.ensure_one()
        self.write({
            'terralab_status': 'accepted',
        })
        next_action = self.env.ref('terralab.accepted_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: Mark order TerraLab status as rejected
    def action_terralab_reject(self):
        # self.ensure_one()
        self.write({
            'terralab_status': 'rejected',
        })
        next_action = self.env.ref('terralab.rejected_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: View test variables related to order
    def action_terralab_view_testvariables(self):
        next_action = self.env.ref('terralab.testvariables_list_action').read()[0]
        next_action['domain'] = [('order_name', '=', self.name)]
        return next_action

    # Order form action: View tests related to order
    def action_terralab_view_tests(self):
        next_action = self.env.ref('terralab.tests_list_action').read()[0]
        next_action['domain'] = [('sample.order', '=', self.id)]
        return next_action

    # Order form action: Calculate test results
    def action_terralab_calculate(self):
        # self.ensure_one()
        self.calculate_all_test_results()
        self.write({
            'terralab_status': 'calculated',
        })
        next_action = self.env.ref('terralab.calculated_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: Generate report
    def action_terralab_generate_report(self):
        self.generate_report()
        self.write({
            'terralab_status': 'report_generated',
        })
        next_action = self.env.ref('terralab.report_generated_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Order form action: Mark order TerraLab status as complete
    def action_terralab_complete(self):
        # self.ensure_one()
        self.write({
            'terralab_status': 'completed',
        })
        next_action = self.env.ref('terralab.completed_orders_list_action').read()[0]
        next_action['target'] = 'main'
        return next_action

    # Calculate test results using spreadsheet
    def calculate_all_test_results(self):
        for order in self:
            for sample in order.terralab_samples:
                for test in sample.tests:
                    test.calculate_test_result()

    # Generate test report
    def generate_report(self):
        Report = self.env['terralab.report']
        for order in self:
            Report.create({
                'order': order.id,
                'generated_at': fields.Datetime.now(),
            })

## Extend Odoo Order Line
#class OrderLine(models.Model):
#    _name = 'sale.order.line'
#    _inherit = 'sale.order.line'
#    terralab_test = fields.Many2one('terralab.test', 'TerraLab Test')
#
#    @api.model
#    def create(self, values):
#        res_id = super(OrderLine, self).create(values)
#        logger.info('Creating Order Line %s' % (values))
#        return res_id
#
#    def write(self, values):
#        super(OrderLine, self).write(values)
#        logger.info('Writing Order Line %s' % (values))
#        return True

class Report(models.Model):
    _name = 'terralab.report'
    _description = 'TerraLab Report'
    order = fields.Many2one('sale.order', 'Order') # A Report is attached to a specific Order
    generated_at = fields.Datetime() # Report generation time

    def name_get(self):
        return [(report.id, '%s %s' % (report.order.name, report.generated_at)) for report in self]
