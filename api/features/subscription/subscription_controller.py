from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from api.features.event.event_schemas import EventReadOut
from api.features.subscription.subscription_schemas import EventSubscriberOut, SubscriptionOut
from api.features.subscription.subscription_service import SubscriptionService
from api.features.user.user import User
from api.shared.dependencies import get_current_user, get_subscription_service

router = APIRouter(prefix="/events", tags=["subscriptions"])


@router.get("/subscriptions/me", response_model=list[EventReadOut])
async def list_my_subscriptions(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> list[EventReadOut]:
    events = await service.list_my_events(current_user)
    return [EventReadOut.model_validate(event) for event in events]


@router.get("/{event_id}/subscribers", response_model=list[EventSubscriberOut])
async def list_event_subscribers(
    event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> list[EventSubscriberOut]:
    subscribers = await service.list_event_subscribers(event_id, current_user)
    return [
        EventSubscriberOut.from_subscription(user, subscribed_at)
        for user, subscribed_at in subscribers
    ]


@router.post(
    "/{event_id}/subscription",
    response_model=SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_event(
    event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> SubscriptionOut:
    subscription = await service.subscribe(event_id, current_user)
    return SubscriptionOut.model_validate(subscription)


@router.delete("/{event_id}/subscription", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_from_event(
    event_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[SubscriptionService, Depends(get_subscription_service)],
) -> Response:
    await service.unsubscribe(event_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
