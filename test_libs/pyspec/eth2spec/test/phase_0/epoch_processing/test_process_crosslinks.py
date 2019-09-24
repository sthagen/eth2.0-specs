from copy import deepcopy

from eth2spec.test.context import spec_state_test, with_all_phases, with_phases
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot
)
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.helpers.attestations import (
    add_attestations_to_state,
    get_valid_attestation,
    sign_attestation)
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with


def run_process_crosslinks(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_crosslinks')


@with_all_phases
@spec_state_test
def test_no_attestations(spec, state):
    yield from run_process_crosslinks(spec, state)

    for shard in range(spec.SHARD_COUNT):
        assert state.previous_crosslinks[shard] == state.current_crosslinks[shard]


@with_all_phases
@spec_state_test
def test_single_crosslink_update_from_current_epoch(spec, state):
    next_epoch(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True)

    add_attestations_to_state(spec, state, [attestation], state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert len(state.current_epoch_attestations) == 1

    shard = attestation.data.crosslink.shard
    pre_crosslink = deepcopy(state.current_crosslinks[shard])

    yield from run_process_crosslinks(spec, state)

    assert state.previous_crosslinks[shard] != state.current_crosslinks[shard]
    assert pre_crosslink != state.current_crosslinks[shard]


@with_all_phases
@spec_state_test
def test_single_crosslink_update_from_previous_epoch(spec, state):
    next_epoch(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True)

    add_attestations_to_state(spec, state, [attestation], state.slot + spec.SLOTS_PER_EPOCH)

    assert len(state.previous_epoch_attestations) == 1

    shard = attestation.data.crosslink.shard
    pre_crosslink = deepcopy(state.current_crosslinks[shard])

    crosslink_deltas = spec.get_crosslink_deltas(state)

    yield from run_process_crosslinks(spec, state)

    assert state.previous_crosslinks[shard] != state.current_crosslinks[shard]
    assert pre_crosslink != state.current_crosslinks[shard]

    # ensure rewarded
    for index in spec.get_crosslink_committee(
            state,
            attestation.data.target.epoch,
            attestation.data.crosslink.shard):
        assert crosslink_deltas[0][index] > 0
        assert crosslink_deltas[1][index] == 0


@with_all_phases
@spec_state_test
def test_double_late_crosslink(spec, state):
    if spec.get_committee_count(state, spec.get_current_epoch(state)) < spec.SHARD_COUNT:
        print("warning: ignoring test, test-assumptions are incompatible with configuration")
        return

    next_epoch(spec, state)
    state.slot += 4

    attestation_1 = get_valid_attestation(spec, state, signed=True)

    # add attestation_1 to next epoch
    next_epoch(spec, state)
    add_attestations_to_state(spec, state, [attestation_1], state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    for _ in range(spec.SLOTS_PER_EPOCH):
        attestation_2 = get_valid_attestation(spec, state)
        if attestation_2.data.crosslink.shard == attestation_1.data.crosslink.shard:
            sign_attestation(spec, state, attestation_2)
            break
        next_slot(spec, state)
    apply_empty_block(spec, state)

    # add attestation_2 in the next epoch after attestation_1 has
    # already updated the relevant crosslink
    next_epoch(spec, state)
    add_attestations_to_state(spec, state, [attestation_2], state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert len(state.previous_epoch_attestations) == 1
    assert len(state.current_epoch_attestations) == 0

    crosslink_deltas = spec.get_crosslink_deltas(state)

    yield from run_process_crosslinks(spec, state)

    shard = attestation_2.data.crosslink.shard

    # ensure that the current crosslinks were not updated by the second attestation
    assert state.previous_crosslinks[shard] == state.current_crosslinks[shard]
    # ensure no reward, only penalties for the failed crosslink
    for index in spec.get_crosslink_committee(
            state,
            attestation_2.data.target.epoch,
            attestation_2.data.crosslink.shard):
        assert crosslink_deltas[0][index] == 0
        assert crosslink_deltas[1][index] > 0


@with_all_phases
@spec_state_test
def test_tied_crosslink_between_epochs(spec, state):
    """
    Addresses scenario found at Interop described by this test case
    https://github.com/djrtwo/interop-test-cases/tree/master/tests/night_one_16_crosslinks

    Ensure that ties on crosslinks between epochs are broken by previous epoch.
    """
    prev_attestation = get_valid_attestation(spec, state)
    sign_attestation(spec, state, prev_attestation)

    # add attestation at start of next epoch
    next_epoch(spec, state)
    add_attestations_to_state(spec, state, [prev_attestation], state.slot)

    # create attestation from current epoch for same shard
    for _ in range(spec.SLOTS_PER_EPOCH):
        cur_attestation = get_valid_attestation(spec, state)
        if cur_attestation.data.crosslink.shard == prev_attestation.data.crosslink.shard:
            sign_attestation(spec, state, cur_attestation)
            break
        next_slot(spec, state)

    add_attestations_to_state(spec, state, [cur_attestation], state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    shard = prev_attestation.data.crosslink.shard
    pre_crosslink = deepcopy(state.current_crosslinks[shard])

    assert prev_attestation.data.crosslink != cur_attestation.data.crosslink
    assert state.current_crosslinks[shard] == spec.Crosslink()
    assert len(state.previous_epoch_attestations) == 1
    assert len(state.current_epoch_attestations) == 1

    yield from run_process_crosslinks(spec, state)

    assert state.previous_crosslinks[shard] != state.current_crosslinks[shard]
    assert pre_crosslink != state.current_crosslinks[shard]
    assert state.current_crosslinks[shard] == prev_attestation.data.crosslink


@with_phases(['phase1'])
@spec_state_test
def test_winning_crosslink_data_root_tie(spec, state):
    """
    Winning crosslink should tie-break on data-root.
    """

    # add attestation at start of next epoch
    next_epoch(spec, state)

    # add 3 equal attestations, all for the same slot, to tie-break on the data-root.
    att1 = get_valid_attestation(spec, state, slot=state.slot - 3)
    att1.data.crosslink.data_root = b'\xbb' * 32
    sign_attestation(spec, state, att1)

    att2 = get_valid_attestation(spec, state, slot=state.slot - 3)
    att2.data.crosslink.data_root = b'\xcc' * 32
    sign_attestation(spec, state, att2)

    att3 = get_valid_attestation(spec, state, slot=state.slot - 3)
    att3.data.crosslink.data_root = b'\xaa' * 32
    sign_attestation(spec, state, att3)

    assert att1.data.crosslink.shard == att2.data.crosslink.shard == att3.data.crosslink.shard
    add_attestations_to_state(spec, state, [att1, att2, att3], state.slot)

    yield from run_process_crosslinks(spec, state)

    assert state.current_crosslinks[att1.data.crosslink.shard].data_root == b'\xcc' * 32
