from eth2spec.test.context import (
    spec_state_test,
    always_bls, never_bls,
    with_all_phases,
    spec_test,
    low_balances,
    with_custom_state,
    single_phase)
from eth2spec.test.helpers.attestations import (
    run_attestation_processing,
    get_valid_attestation,
    sign_aggregate_attestation,
    sign_attestation,
)
from eth2spec.test.helpers.state import (
    next_slot,
    next_slots,
    next_epoch,
    transition_to,
)
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.utils.ssz.ssz_typing import Bitlist


@with_all_phases
@spec_state_test
def test_success(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_test
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@single_phase
def test_success_multi_proposer_index_iterations(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_success_previous_epoch(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True, on_time=False)
    transition_to(spec, state, spec.SLOTS_PER_EPOCH - 1)
    next_epoch(spec, state)
    apply_empty_block(spec, state)

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
@always_bls
def test_invalid_attestation_signature(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_before_inclusion_delay(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    # do not increment slot to allow for inclusion delay

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_after_epoch_slots(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True, on_time=False)

    # increment past latest inclusion slot
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH + 1)
    apply_empty_block(spec, state)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_old_source_epoch(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 5)
    state.finalized_checkpoint.epoch = 2
    state.previous_justified_checkpoint.epoch = 3
    state.current_justified_checkpoint.epoch = 4
    attestation = get_valid_attestation(spec, state, slot=(spec.SLOTS_PER_EPOCH * 3) + 1)

    # test logic sanity check: make sure the attestation is pointing to oldest known source epoch
    assert attestation.data.source.epoch == state.previous_justified_checkpoint.epoch

    # Now go beyond that, it will be invalid
    attestation.data.source.epoch -= 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
@always_bls
def test_wrong_index_for_committee_signature(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.index += 1

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
@never_bls
def test_wrong_index_for_slot(spec, state):
    while spec.get_committee_count_at_slot(state, state.slot) >= spec.MAX_COMMITTEES_PER_SLOT:
        state.validators = state.validators[:len(state.validators) // 2]
        state.balances = state.balances[:len(state.balances) // 2]

    index = spec.MAX_COMMITTEES_PER_SLOT - 1

    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.index = index

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
@never_bls
def test_invalid_index(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # off by one (with respect to valid range) on purpose
    attestation.data.index = spec.MAX_COMMITTEES_PER_SLOT

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_mismatched_target_and_slot(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)

    attestation = get_valid_attestation(spec, state, on_time=False)
    attestation.data.slot = attestation.data.slot - spec.SLOTS_PER_EPOCH

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_old_target_epoch(spec, state):
    assert spec.MIN_ATTESTATION_INCLUSION_DELAY < spec.SLOTS_PER_EPOCH * 2

    attestation = get_valid_attestation(spec, state, signed=True, on_time=False)

    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 2)  # target epoch will be too old to handle

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_future_target_epoch(spec, state):
    assert spec.MIN_ATTESTATION_INCLUSION_DELAY < spec.SLOTS_PER_EPOCH * 2

    attestation = get_valid_attestation(spec, state)

    participants = spec.get_attesting_indices(
        state,
        attestation.data,
        attestation.aggregation_bits
    )
    attestation.data.target.epoch = spec.get_current_epoch(state) + 1  # target epoch will be too new to handle

    # manually add signature for correct participants
    attestation.signature = sign_aggregate_attestation(spec, state, attestation.data, participants)

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_new_source_epoch(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.epoch += 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_source_root_is_target_root(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.root = attestation.data.target.root

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_invalid_current_source_root(spec, state):
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 5)

    state.finalized_checkpoint.epoch = 2

    state.previous_justified_checkpoint = spec.Checkpoint(epoch=3, root=b'\x01' * 32)
    state.current_justified_checkpoint = spec.Checkpoint(epoch=4, root=b'\x32' * 32)

    attestation = get_valid_attestation(spec, state, slot=(spec.SLOTS_PER_EPOCH * 3) + 1, on_time=False)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Test logic sanity checks:
    assert state.current_justified_checkpoint.root != state.previous_justified_checkpoint.root
    assert attestation.data.source.root == state.previous_justified_checkpoint.root

    # Make attestation source root invalid: should be previous justified, not current one
    attestation.data.source.root = state.current_justified_checkpoint.root

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_bad_source_root(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.source.root = b'\x42' * 32

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_empty_aggregation_bits(spec, state):
    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, empty=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert attestation.aggregation_bits == Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
        *([0b0] * len(attestation.aggregation_bits)))

    yield from run_attestation_processing(spec, state, attestation)


@with_all_phases
@spec_state_test
def test_too_many_aggregation_bits(spec, state):
    attestation = get_valid_attestation(spec, state, signed=True)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # one too many bits
    attestation.aggregation_bits.append(0b0)

    yield from run_attestation_processing(spec, state, attestation, False)


@with_all_phases
@spec_state_test
def test_too_few_aggregation_bits(spec, state):
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.aggregation_bits = Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
        *([0b1] + [0b0] * (len(attestation.aggregation_bits) - 1)))

    sign_attestation(spec, state, attestation)

    # one too few bits
    attestation.aggregation_bits = attestation.aggregation_bits[:-1]

    yield from run_attestation_processing(spec, state, attestation, False)
