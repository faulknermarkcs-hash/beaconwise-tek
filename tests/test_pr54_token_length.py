from ecosphere.config import Settings
from ecosphere.kernel.session import SessionState, Profile, PendingGate
from ecosphere.kernel.gates import set_pending_gate


def test_token_length_profile_dependent():
    s = SessionState(session_id="s1")
    s.interaction_count = 1

    s.current_profile = Profile.A_FAST.value
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    assert len(s.pending_gate.confirm_token) == Settings.TOKENLEN_FAST

    s.current_profile = Profile.A_STANDARD.value
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    assert len(s.pending_gate.confirm_token) == Settings.TOKENLEN_STANDARD

    s.current_profile = Profile.A_HIGH_ASSURANCE.value
    set_pending_gate(s, PendingGate.REFLECT_CONFIRM.value, {"x": 1})
    assert len(s.pending_gate.confirm_token) == Settings.TOKENLEN_HIGH

