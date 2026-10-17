"""Per-table Staff admission policy. Pure domain code, no fake friend identities."""
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class StaffPolicy:
    mode: str = 'disabled'   # disabled | when_human_waiting | demonstration
    max_staff: int = 1
    max_staff_tables: int = 1

@dataclass(frozen=True)
class Table:
    id: str
    capacity: int
    humans: int
    staff: int = 0
    allow_staff: bool = False
    ranked: bool = False

def plan_staff(tables:list[Table], policy:StaffPolicy)->dict[str,int]:
    """Only allocates Staff to permitted tables. Never changes reported human count."""
    if policy.mode not in ('disabled','when_human_waiting','demonstration'):
        raise ValueError('invalid mode')
    if policy.max_staff<0 or policy.max_staff_tables<0:
        raise ValueError('negative staff budget')
    if policy.mode=='disabled':return {}
    eligible=[]
    for t in tables:
        if t.capacity<2 or t.capacity>8 or min(t.humans,t.staff)<0 or t.humans+t.staff>t.capacity:
            raise ValueError('invalid occupancy')
        if t.ranked or not t.allow_staff or t.staff>=policy.max_staff:continue
        if policy.mode=='when_human_waiting' and t.humans<1:continue
        if t.capacity<=t.humans+t.staff:continue
        eligible.append(t)
    # Deterministic ordering, no random flapping/reconciliation churn.
    eligible.sort(key=lambda t:(-t.humans,t.id))
    return {t.id:min(policy.max_staff-t.staff,t.capacity-t.humans-t.staff) for t in eligible[:policy.max_staff_tables]}

def staff_public_profile(staff_id:str,display_name:str)->dict:
    if not staff_id.startswith('staff:'):raise ValueError('non-staff actor')
    return {'id':staff_id,'displayName':display_name,'label':'Staff','actorType':'staff_bot',
            'computerControlled':True,'canFriend':False,'canMessage':False,'isModerator':False}
