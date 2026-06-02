from sqlalchemy.orm import Session

from app.models.known_person import KnownPerson


def create_known_person(
    db: Session,
    *,
    full_name: str,
    reference_image_path: str | None = None,
    notes: str | None = None,
    is_active: bool = True,
) -> KnownPerson:
    person = KnownPerson(
        full_name=full_name,
        reference_image_path=reference_image_path,
        notes=notes,
        is_active=is_active,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_known_person_by_id(db: Session, person_id: int) -> KnownPerson | None:
    return db.query(KnownPerson).filter(KnownPerson.id == person_id).first()


def list_known_persons(
    db: Session,
    *,
    only_active: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> list[KnownPerson]:
    query = db.query(KnownPerson)
    if only_active:
        query = query.filter(KnownPerson.is_active.is_(True))

    return query.order_by(KnownPerson.full_name.asc()).offset(skip).limit(limit).all()


def update_known_person(
    db: Session,
    *,
    person_id: int,
    full_name: str | None = None,
    reference_image_path: str | None = None,
    notes: str | None = None,
    is_active: bool | None = None,
) -> KnownPerson | None:
    person = get_known_person_by_id(db, person_id)
    if person is None:
        return None

    if full_name is not None:
        person.full_name = full_name
    if reference_image_path is not None:
        person.reference_image_path = reference_image_path
    if notes is not None:
        person.notes = notes
    if is_active is not None:
        person.is_active = is_active

    db.commit()
    db.refresh(person)
    return person


def delete_known_person(db: Session, person_id: int) -> bool:
    person = get_known_person_by_id(db, person_id)
    if person is None:
        return False

    db.delete(person)
    db.commit()
    return True
