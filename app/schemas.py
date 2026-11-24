import re
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, EmailStr, BeforeValidator, model_validator

from app.errors import ApiError


def json_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('Use a JSON number, not a string or boolean.')
    return Decimal(str(value))


Number = Annotated[Decimal, BeforeValidator(json_number)]
Phone = Annotated[str, Field(pattern=r'^\+[1-9]\d{7,14}$')]
Material = Literal['gravel', 'sand', 'crushed_stone']
Status = Literal['pending', 'confirmed', 'delivered', 'cancelled']


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class QuarryBody(Body):
    name: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=80)
    address: str = Field(min_length=5, max_length=200)
    phone: Phone
    description: str = Field(min_length=5, max_length=1000)
    latitude: Number = Field(ge=-90, le=90)
    longitude: Number = Field(ge=-180, le=180)


class QuarryPatchBody(Body):
    """Allow omitted fields, but reject explicit nulls and empty updates."""
    name: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=80)
    address: str | None = Field(default=None, min_length=5, max_length=200)
    phone: Phone | None = None
    description: str | None = Field(default=None, min_length=5, max_length=1000)
    latitude: Number | None = Field(default=None, ge=-90, le=90)
    longitude: Number | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode='after')
    def check_patch_fields(self):
        if not self.model_fields_set:
            raise ValueError('Provide at least one field to update.')
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError('Updated fields cannot be null.')
        return self


class OfferBody(Body):
    name: str = Field(min_length=2, max_length=100)
    materialType: Material
    fraction: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=5, max_length=1000)
    pricePerTonneEur: Number = Field(ge=Decimal('.01'), le=Decimal('999999.99'), multiple_of=Decimal('.01'))
    available: bool = Field(strict=True)


class OrderBody(Body):
    customerName: str = Field(min_length=2, max_length=100)
    email: EmailStr = Field(max_length=254)
    phone: Phone
    deliveryAddress: str = Field(min_length=5, max_length=200)
    quantityTonnes: Number = Field(ge=Decimal('.001'), le=1000, multiple_of=Decimal('.001'))
    willBeHome: bool = Field(strict=True)
    unloadingInstructions: str = Field(max_length=1000)
    paymentMethod: Literal['card', 'cash']
    status: Status

    @model_validator(mode='after')
    def check_instructions(self):
        if not self.willBeHome and not self.unloadingInstructions:
            raise ValueError('Instructions are required when the customer will not be home.')
        return self


def positive_id(raw):
    if not re.fullmatch(r'[1-9][0-9]*', str(raw)) or len(str(raw)) > 10 or int(raw) > 2147483647:
        raise ApiError(400, 'VALIDATION_ERROR', 'ID must be a positive 32-bit integer.')
    return int(raw)


def filters(request: Request, kind=None):
    allowed = {
        'quarry': {'city', 'search'}, 'offer': {'materialType', 'available', 'minPrice', 'maxPrice'},
        'order': {'status', 'paymentMethod'}, None: set(),
    }[kind] | ({'page', 'pageSize'} if kind else set())
    items = list(request.query_params.multi_items())
    values = dict(items)
    if len(items) != len(values) or set(values) - allowed:
        raise ApiError(400, 'VALIDATION_ERROR', 'Unknown or repeated query parameters.')
    if not kind:
        return {}
    for key, default, maximum in [('page', '1', 100000), ('pageSize', '10', 100)]:
        raw = values.get(key, default)
        if not re.fullmatch(r'[1-9][0-9]*', raw) or len(raw) > 6 or int(raw) > maximum:
            raise ApiError(400, 'VALIDATION_ERROR', f'Invalid {key}. Maximum is {maximum}.')
        values[key] = int(raw)
    for key, maximum in [('city', 80), ('search', 100)]:
        if key in values:
            values[key] = values[key].strip()
            if not 1 <= len(values[key]) <= maximum:
                raise ApiError(400, 'VALIDATION_ERROR', f'Invalid {key}.')
    for key, choices in [('materialType', ('gravel', 'sand', 'crushed_stone')),
                         ('status', ('pending', 'confirmed', 'delivered', 'cancelled')),
                         ('paymentMethod', ('cash', 'card')), ('available', ('true', 'false'))]:
        if key in values and values[key] not in choices:
            raise ApiError(400, 'VALIDATION_ERROR', f'Invalid {key}.')
    if 'available' in values:
        values['available'] = values['available'] == 'true'
    for key in ('minPrice', 'maxPrice'):
        if key in values:
            raw = values[key]
            if len(raw) > 12 or not re.fullmatch(r'[0-9]+(\.[0-9]{1,2})?', raw) or Decimal(raw) > Decimal('999999.99'):
                raise ApiError(400, 'VALIDATION_ERROR', f'Invalid {key}.')
            values[key] = Decimal(raw)
    if values.get('minPrice', 0) > values.get('maxPrice', Decimal('999999.99')):
        raise ApiError(400, 'VALIDATION_ERROR', 'maxPrice must be greater than or equal to minPrice.')
    return values
