from pydantic import BaseModel

from app.utils.enums import OperationMode


class OperationModeRead(BaseModel):
    operation_mode: OperationMode


class OperationModeUpdate(BaseModel):
    operation_mode: OperationMode
