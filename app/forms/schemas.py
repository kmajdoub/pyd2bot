from marshmallow import Schema, ValidationError, fields, post_load
from pyd2bot.models.session.models import JobFilter, SessionType


class JobFilterSchema(Schema):
    jobId = fields.Int(required=True)
    resourcesIds = fields.List(fields.Int(), required=True)

    @post_load
    def make_job_filter(self, data, **kwargs):
        return JobFilter.from_dict(data)


class FarmSessionSchema(Schema):
    accountId = fields.Int(required=True)
    characterId = fields.Float(required=True)
    type = fields.Method("get_session_type", deserialize="load_session_type")
    pathId = fields.Str(allow_none=True)
    pathsIds = fields.List(fields.Str(), allow_none=True)
    jobFilters = fields.List(fields.Nested(JobFilterSchema), required=True)

    def get_session_type(self, obj):
        return obj.value

    def load_session_type(self, value):
        try:
            return SessionType(int(value))
        except ValueError:
            raise ValidationError(f"{value} is not a valid SessionType")


class FightSessionSchema(Schema):
    accountId = fields.Int(required=True)
    characterId = fields.Float(required=True)
    type = fields.Method("get_session_type", deserialize="load_session_type")
    pathId = fields.Str(allow_none=True)
    monsterLvlCoefDiff = fields.Float(required=True)

    def get_session_type(self, obj):
        return obj.value

    def load_session_type(self, value):
        try:
            return SessionType(int(value))
        except ValueError:
            raise ValidationError(f"{value} is not a valid SessionType")
