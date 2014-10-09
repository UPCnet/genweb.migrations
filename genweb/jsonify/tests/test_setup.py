# -*- coding: utf-8 -*-
"""Setup/installation tests for this package."""

from genweb.jsonify.testing import IntegrationTestCase
from plone import api


class TestInstall(IntegrationTestCase):
    """Test installation of genweb.jsonify into Plone."""

    def setUp(self):
        """Custom shared utility setup for tests."""
        self.portal = self.layer['portal']
        self.installer = api.portal.get_tool('portal_quickinstaller')

    def test_product_installed(self):
        """Test if genweb.jsonify is installed with portal_quickinstaller."""
        self.assertTrue(self.installer.isProductInstalled('genweb.jsonify'))

    def test_uninstall(self):
        """Test if genweb.jsonify is cleanly uninstalled."""
        self.installer.uninstallProducts(['genweb.jsonify'])
        self.assertFalse(self.installer.isProductInstalled('genweb.jsonify'))

    # browserlayer.xml
    def test_browserlayer(self):
        """Test that IGenwebJsonifyLayer is registered."""
        from genweb.jsonify.interfaces import IGenwebJsonifyLayer
        from plone.browserlayer import utils
        self.failUnless(IGenwebJsonifyLayer in utils.registered_layers())
