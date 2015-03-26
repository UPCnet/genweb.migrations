from datetime import datetime

from zope.component import adapts
from zope.interface import implements

from zope.schema.interfaces import IDatetime
from plone.app.event.base import default_timezone
from transmogrify.dexterity.interfaces import IDeserializer


class DatetimeDeserializer(object):
    implements(IDeserializer)
    adapts(IDatetime)

    def __init__(self, field):
        self.field = field

    def __call__(self, value, filestore, item,
                 disable_constraints=False, logger=None):
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, basestring):
            # Fix some rare use case
            if 'Universal' in value:
                value = value.replace('Universal', 'UTC')

            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M')
            except:
                value = datetime.now()

            # Fix timezone
            tz_default = default_timezone(as_tzinfo=True)
            if value.tzinfo is None:
                value = tz_default.localize(value)
        try:
            self.field.validate(value)
        except Exception, e:
            if not disable_constraints:
                raise e
            else:
                if logger:
                    logger(
                        "%s is invalid in %s: %s" % (
                            self.field.__name__,
                            item['_path'],
                            e)
                    )
        return value
