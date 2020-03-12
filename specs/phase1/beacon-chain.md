# Ethereum 2.0 Phase 1 -- The Beacon Chain for Shards

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
- [Updated containers](#updated-containers)
  - [Extended `AttestationData`](#extended-attestationdata)
  - [Extended `Attestation`](#extended-attestation)
  - [Extended `PendingAttestation`](#extended-pendingattestation)
  - [`IndexedAttestation`](#indexedattestation)
    - [Extended `AttesterSlashing`](#extended-attesterslashing)
  - [Extended `Validator`](#extended-validator)
  - [Extended `BeaconBlockBody`](#extended-beaconblockbody)
  - [Extended `BeaconBlock`](#extended-beaconblock)
    - [Extended `SignedBeaconBlock`](#extended-signedbeaconblock)
  - [Extended `BeaconState`](#extended-beaconstate)
- [New containers](#new-containers)
  - [`ShardBlockWrapper`](#shardblockwrapper)
  - [`ShardSignableHeader`](#shardsignableheader)
  - [`ShardState`](#shardstate)
  - [`ShardTransition`](#shardtransition)
  - [`CompactCommittee`](#compactcommittee)
  - [`AttestationCustodyBitWrapper`](#attestationcustodybitwrapper)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
    - [`get_previous_slot`](#get_previous_slot)
    - [`pack_compact_validator`](#pack_compact_validator)
    - [`committee_to_compact_committee`](#committee_to_compact_committee)
    - [`compute_shard_from_committee_index`](#compute_shard_from_committee_index)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_active_shard_count`](#get_active_shard_count)
    - [`get_online_validator_indices`](#get_online_validator_indices)
    - [`get_shard_committee`](#get_shard_committee)
    - [`get_shard_proposer_index`](#get_shard_proposer_index)
    - [`get_light_client_committee`](#get_light_client_committee)
    - [`get_indexed_attestation`](#get_indexed_attestation)
    - [`get_updated_gasprice`](#get_updated_gasprice)
    - [`get_start_shard`](#get_start_shard)
    - [`get_shard`](#get_shard)
    - [`get_next_slot_for_shard`](#get_next_slot_for_shard)
    - [`get_offset_slots`](#get_offset_slots)
  - [Predicates](#predicates)
    - [Updated `is_valid_indexed_attestation`](#updated-is_valid_indexed_attestation)
  - [Block processing](#block-processing)
    - [Operations](#operations)
      - [New Attestation processing](#new-attestation-processing)
        - [`validate_attestation`](#validate_attestation)
        - [`apply_shard_transition`](#apply_shard_transition)
        - [`process_crosslink_for_shard`](#process_crosslink_for_shard)
        - [`process_crosslinks`](#process_crosslinks)
        - [`process_attestations`](#process_attestations)
      - [New Attester slashing processing](#new-attester-slashing-processing)
    - [Shard transition false positives](#shard-transition-false-positives)
    - [Light client processing](#light-client-processing)
  - [Epoch transition](#epoch-transition)
    - [Custody game updates](#custody-game-updates)
    - [Online-tracking](#online-tracking)
    - [Light client committee updates](#light-client-committee-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the extensions made to the Phase 0 design of The Beacon Chain
 to facilitate the new shards as part of Phase 1 of Eth2.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `Shard` | `uint64` | a shard number |
| `OnlineEpochs` | `uint8` | online countdown epochs |

## Configuration

Configuration is not namespaced. Instead it is strictly an extension;
 no constants of phase 0 change, but new constants are adopted for changing behaviors.

### Misc

| Name | Value | Unit | Duration |
| - | - | - | - | 
| `MAX_SHARDS` | `2**10` (= 1024) |
| `ONLINE_PERIOD` | `OnlineEpochs(2**3)` (= 8) | online epochs | ~51 min |
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `LIGHT_CLIENT_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |
| `SHARD_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |
| `MAX_SHARD_BLOCK_SIZE` | `2**20` (= 1,048,576) | |
| `TARGET_SHARD_BLOCK_SIZE` | `2**18` (= 262,144) | |
| `SHARD_BLOCK_OFFSETS` | `[1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233]` | |
| `MAX_SHARD_BLOCKS_PER_ATTESTATION` | `len(SHARD_BLOCK_OFFSETS)` | |
| `MAX_GASPRICE` | `Gwei(2**14)` (= 16,384) | Gwei | |
| `MIN_GASPRICE` | `Gwei(2**5)` (= 32) | Gwei | |
| `GASPRICE_ADJUSTMENT_COEFFICIENT` | `2**3` (= 8) | |
| `DOMAIN_SHARD_PROPOSAL` | `DomainType('0x80000000')` | |
| `DOMAIN_SHARD_COMMITTEE` | `DomainType('0x81000000')` | |
| `DOMAIN_LIGHT_CLIENT` | `DomainType('0x82000000')` | |

## Updated containers

The following containers have updated definitions in Phase 1.

### Extended `AttestationData`

```python
class AttestationData(Container):
    slot: Slot
    index: CommitteeIndex
    # LMD GHOST vote
    beacon_block_root: Root
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Current-slot shard block root
    head_shard_root: Root
    # Shard transition root
    shard_transition_root: Root
```

### Extended `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    custody_bits_blocks: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_SHARD_BLOCKS_PER_ATTESTATION]
    signature: BLSSignature
```

### Extended `PendingAttestation`

```python
class PendingAttestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    inclusion_delay: Slot
    proposer_index: ValidatorIndex
    crosslink_success: boolean
```

### `IndexedAttestation`

```python
class IndexedAttestation(Container):
    committee: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]
    attestation: Attestation
```

#### Extended `AttesterSlashing`

Note that the `attestation_1` and `attestation_2` have a new `IndexedAttestation` definition.

```python
class AttesterSlashing(Container):
    attestation_1: IndexedAttestation
    attestation_2: IndexedAttestation
```

### Extended `Validator`

```python
class Validator(Container):
    pubkey: BLSPubkey
    withdrawal_credentials: Bytes32  # Commitment to pubkey for withdrawals
    effective_balance: Gwei  # Balance at stake
    slashed: boolean
    # Status epochs
    activation_eligibility_epoch: Epoch  # When criteria for activation were met
    activation_epoch: Epoch
    exit_epoch: Epoch
    withdrawable_epoch: Epoch  # When validator can withdraw funds
    # Custody game
    # next_custody_secret_to_reveal is initialised to the custody period
    # (of the particular validator) in which the validator is activated
    # = get_custody_period_for_validator(...)
    next_custody_secret_to_reveal: uint64
    max_reveal_lateness: Epoch
```

### Extended `BeaconBlockBody`

```python
class BeaconBlockBody(Container):
    randao_reveal: BLSSignature
    eth1_data: Eth1Data  # Eth1 data vote
    graffiti: Bytes32  # Arbitrary data
    # Slashings
    proposer_slashings: List[ProposerSlashing, MAX_PROPOSER_SLASHINGS]
    attester_slashings: List[AttesterSlashing, MAX_ATTESTER_SLASHINGS]
    # Attesting
    attestations: List[Attestation, MAX_ATTESTATIONS]
    # Entry & exit
    deposits: List[Deposit, MAX_DEPOSITS]
    voluntary_exits: List[SignedVoluntaryExit, MAX_VOLUNTARY_EXITS]
    # Custody game
    custody_slashings: List[SignedCustodySlashing, MAX_CUSTODY_SLASHINGS]
    custody_key_reveals: List[CustodyKeyReveal, MAX_CUSTODY_KEY_REVEALS]
    early_derived_secret_reveals: List[EarlyDerivedSecretReveal, MAX_EARLY_DERIVED_SECRET_REVEALS]
    # Shards
    shard_transitions: Vector[ShardTransition, MAX_SHARDS]
    # Light clients
    light_client_signature_bitfield: Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
```

### Extended `BeaconBlock`

Note that the `body` has a new `BeaconBlockBody` definition.

```python
class BeaconBlock(Container):
    slot: Slot
    proposer_index: ValidatorIndex
    parent_root: Root
    state_root: Root
    body: BeaconBlockBody
```

#### Extended `SignedBeaconBlock`

Note that the `message` has a new `BeaconBlock` definition.

```python
class SignedBeaconBlock(Container):
    message: BeaconBlock
    signature: BLSSignature
```

### Extended `BeaconState`

Note that aside from the new additions, `Validator` and `PendingAttestation` have new definitions.

```python
class BeaconState(Container):
    # Versioning
    genesis_time: uint64
    genesis_validators_root: Root
    slot: Slot
    fork: Fork
    # History
    latest_block_header: BeaconBlockHeader
    block_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    state_roots: Vector[Root, SLOTS_PER_HISTORICAL_ROOT]
    historical_roots: List[Root, HISTORICAL_ROOTS_LIMIT]
    # Eth1
    eth1_data: Eth1Data
    eth1_data_votes: List[Eth1Data, EPOCHS_PER_ETH1_VOTING_PERIOD * SLOTS_PER_EPOCH]
    eth1_deposit_index: uint64
    # Registry
    validators: List[Validator, VALIDATOR_REGISTRY_LIMIT]
    balances: List[Gwei, VALIDATOR_REGISTRY_LIMIT]
    # Randomness
    randao_mixes: Vector[Root, EPOCHS_PER_HISTORICAL_VECTOR]
    # Slashings
    slashings: Vector[Gwei, EPOCHS_PER_SLASHINGS_VECTOR]  # Per-epoch sums of slashed effective balances
    # Attestations
    previous_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    current_epoch_attestations: List[PendingAttestation, MAX_ATTESTATIONS * SLOTS_PER_EPOCH]
    # Finality
    justification_bits: Bitvector[JUSTIFICATION_BITS_LENGTH]  # Bit set for every recent justified epoch
    previous_justified_checkpoint: Checkpoint  # Previous epoch snapshot
    current_justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    # Phase 1
    shard_states: List[ShardState, MAX_SHARDS]
    online_countdown: List[OnlineEpochs, VALIDATOR_REGISTRY_LIMIT]  # not a raw byte array, considered its large size.
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
    # Custody game
    # Future derived secrets already exposed; contains the indices of the exposed validator
    # at RANDAO reveal period % EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS
    exposed_derived_secrets: Vector[List[ValidatorIndex, MAX_EARLY_DERIVED_SECRET_REVEALS * SLOTS_PER_EPOCH],
                                    EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS]
```

## New containers

The following containers are new in Phase 1.

### `ShardBlockWrapper`

_Wrapper for being broadcasted over the network._

```python
class ShardBlockWrapper(Container):
    shard_parent_root: Root
    beacon_parent_root: Root
    slot: Slot
    body: ByteList[MAX_SHARD_BLOCK_SIZE]
    signature: BLSSignature
```

### `ShardSignableHeader`

```python
class ShardSignableHeader(Container):
    shard_parent_root: Root
    beacon_parent_root: Root
    slot: Slot
    body_root: Root
```

### `ShardState`

```python
class ShardState(Container):
    slot: Slot
    gasprice: Gwei
    data: Bytes32
    latest_block_root: Root
```

### `ShardTransition`

```python
class ShardTransition(Container):
    # Starting from slot
    start_slot: Slot
    # Shard block lengths
    shard_block_lengths: List[uint64, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Shard data roots
    shard_data_roots: List[Bytes32, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Intermediate shard states
    shard_states: List[ShardState, MAX_SHARD_BLOCKS_PER_ATTESTATION]
    # Proposer signature aggregate
    proposer_signature_aggregate: BLSSignature
```

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

### `AttestationCustodyBitWrapper`

```python
class AttestationCustodyBitWrapper(Container):
    attestation_data_root: Root
    block_index: uint64
    bit: boolean
```

## Helper functions

### Misc

#### `get_previous_slot`

```python
def get_previous_slot(slot: Slot) -> Slot:
    if slot > 0:
        return Slot(slot - 1)
    else:
        return Slot(0)
```

#### `pack_compact_validator`

```python
def pack_compact_validator(index: int, slashed: bool, balance_in_increments: int) -> int:
    """
    Creates a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

#### `committee_to_compact_committee`

```python
def committee_to_compact_committee(state: BeaconState, committee: Sequence[ValidatorIndex]) -> CompactCommittee:
    """
    Given a state and a list of validator indices, outputs the CompactCommittee representing them.
    """
    validators = [state.validators[i] for i in committee]
    compact_validators = [
        pack_compact_validator(i, v.slashed, v.effective_balance // EFFECTIVE_BALANCE_INCREMENT)
        for i, v in zip(committee, validators)
    ]
    pubkeys = [v.pubkey for v in validators]
    return CompactCommittee(pubkeys=pubkeys, compact_validators=compact_validators)
```

#### `compute_shard_from_committee_index`

```python
def compute_shard_from_committee_index(state: BeaconState, index: CommitteeIndex, slot: Slot) -> Shard:
    active_shards = get_active_shard_count(state)
    return Shard((index + get_start_shard(state, slot)) % active_shards)
```

### Beacon state accessors

#### `get_active_shard_count`

```python
def get_active_shard_count(state: BeaconState) -> uint64:
    return len(state.shard_states)  # May adapt in the future, or change over time.
```

#### `get_online_validator_indices`

```python
def get_online_validator_indices(state: BeaconState) -> Set[ValidatorIndex]:
    active_validators = get_active_validator_indices(state, get_current_epoch(state))
    return set([i for i in active_validators if state.online_countdown[i] != 0])
```

#### `get_shard_committee`

```python
def get_shard_committee(beacon_state: BeaconState, epoch: Epoch, shard: Shard) -> Sequence[ValidatorIndex]:
    source_epoch = epoch - epoch % SHARD_COMMITTEE_PERIOD 
    if source_epoch > 0:
        source_epoch -= SHARD_COMMITTEE_PERIOD
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_SHARD_COMMITTEE)
    return compute_committee(active_validator_indices, seed, shard, get_active_shard_count(beacon_state))
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(beacon_state: BeaconState, slot: Slot, shard: Shard) -> ValidatorIndex:
    committee = get_shard_committee(beacon_state, compute_epoch_at_slot(slot), shard)
    r = bytes_to_int(get_seed(beacon_state, get_current_epoch(beacon_state), DOMAIN_SHARD_COMMITTEE)[:8])
    return committee[r % len(committee)]
```

#### `get_light_client_committee`

```python
def get_light_client_committee(beacon_state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    source_epoch = epoch - epoch % LIGHT_CLIENT_COMMITTEE_PERIOD 
    if source_epoch > 0:
        source_epoch -= LIGHT_CLIENT_COMMITTEE_PERIOD
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_LIGHT_CLIENT)
    active_shards = get_active_shard_count(beacon_state)
    return compute_committee(active_validator_indices, seed, 0, active_shards)[:TARGET_COMMITTEE_SIZE]
```

#### `get_indexed_attestation`

```python
def get_indexed_attestation(beacon_state: BeaconState, attestation: Attestation) -> IndexedAttestation:
    committee = get_beacon_committee(beacon_state, attestation.data.slot, attestation.data.index)
    return IndexedAttestation(
        committee=committee,
        attestation=attestation,
    )
```

#### `get_updated_gasprice`

```python
def get_updated_gasprice(prev_gasprice: Gwei, length: uint8) -> Gwei:
    if length > TARGET_SHARD_BLOCK_SIZE:
        delta = (prev_gasprice * (length - TARGET_SHARD_BLOCK_SIZE) 
                 // TARGET_SHARD_BLOCK_SIZE // GASPRICE_ADJUSTMENT_COEFFICIENT)
        return min(prev_gasprice + delta, MAX_GASPRICE)
    else:
        delta = (prev_gasprice * (TARGET_SHARD_BLOCK_SIZE - length)
                 // TARGET_SHARD_BLOCK_SIZE // GASPRICE_ADJUSTMENT_COEFFICIENT)
        return max(prev_gasprice, MIN_GASPRICE + delta) - delta
```

#### `get_start_shard`

```python
def get_start_shard(state: BeaconState, slot: Slot) -> Shard:
    # TODO: implement start shard logic
    return Shard(0)
```

#### `get_shard`

```python
def get_shard(state: BeaconState, attestation: Attestation) -> Shard:
    return compute_shard_from_committee_index(state, attestation.data.index, attestation.data.slot)
```

#### `get_next_slot_for_shard`

```python
def get_next_slot_for_shard(state: BeaconState, shard: Shard) -> Slot:
    return Slot(state.shard_states[shard].slot + 1)
```


#### `get_offset_slots`

```python
def get_offset_slots(state: BeaconState, start_slot: Slot) -> Sequence[Slot]:
    return [Slot(start_slot + x) for x in SHARD_BLOCK_OFFSETS if start_slot + x < state.slot]
```

### Predicates

#### Updated `is_valid_indexed_attestation`

Note that this replaces the Phase 0 `is_valid_indexed_attestation`.

```python
def is_valid_indexed_attestation(state: BeaconState, indexed_attestation: IndexedAttestation) -> bool:
    """
    Check if ``indexed_attestation`` has valid indices and signature.
    """
    # Verify aggregate signature
    all_pubkeys = []
    all_signing_roots = []
    attestation = indexed_attestation.attestation
    domain = get_domain(state, DOMAIN_BEACON_ATTESTER, attestation.data.target.epoch)
    aggregation_bits = attestation.aggregation_bits
    assert len(aggregation_bits) == len(indexed_attestation.committee)
    
    if len(attestation.custody_bits_blocks) == 0:
        # fall back on phase0 behavior if there is no shard data.
        for participant, abit in zip(indexed_attestation.committee, aggregation_bits):
            if abit:
                all_pubkeys.append(state.validators[participant].pubkey)
        signing_root = compute_signing_root(indexed_attestation.attestation.data, domain)
        return bls.FastAggregateVerify(all_pubkeys, signing_root, signature=attestation.signature)
    else:
        for i, custody_bits in enumerate(attestation.custody_bits_blocks):
            assert len(custody_bits) == len(indexed_attestation.committee)
            for participant, abit, cbit in zip(indexed_attestation.committee, aggregation_bits, custody_bits):
                if abit:
                    all_pubkeys.append(state.validators[participant].pubkey)
                    # Note: only 2N distinct message hashes
                    all_signing_roots.append(compute_signing_root(
                        AttestationCustodyBitWrapper(hash_tree_root(attestation.data), i, cbit), domain))
                else:
                    assert not cbit
        return bls.AggregateVerify(zip(all_pubkeys, all_signing_roots), signature=attestation.signature)
```


### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    verify_shard_transition_false_positives(state, block.body)
    process_light_client_signatures(state, block.body)
    process_operations(state, block.body)
```


#### Operations

```python
def process_operations(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify that outstanding deposits are processed up to the maximum number of deposits
    assert len(body.deposits) == min(MAX_DEPOSITS, state.eth1_data.deposit_count - state.eth1_deposit_index)
    
    def for_ops(operations: Sequence[Any], fn: Callable[[BeaconState, Any], None]) -> None:
        for operation in operations:
            fn(state, operation)
    
    for_ops(body.proposer_slashings, process_proposer_slashing)
    for_ops(body.attester_slashings, process_attester_slashing)

    # New attestation processing
    process_attestations(state, body, body.attestations)

    for_ops(body.deposits, process_deposit)
    for_ops(body.voluntary_exits, process_voluntary_exit)

    # See custody game spec.
    process_custody_game_operations(state, body)

    # TODO process_operations(body.shard_receipt_proofs, process_shard_receipt_proofs)
```

##### New Attestation processing

###### `validate_attestation`

```python
def validate_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert data.index < get_committee_count_at_slot(state, data.slot)
    assert data.index < get_active_shard_count(state)
    assert data.target.epoch in (get_previous_epoch(state), get_current_epoch(state))
    assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY <= state.slot <= data.slot + SLOTS_PER_EPOCH

    committee = get_beacon_committee(state, data.slot, data.index)
    assert len(attestation.aggregation_bits) == len(committee)

    if attestation.data.target.epoch == get_current_epoch(state):
        assert attestation.data.source == state.current_justified_checkpoint
    else:
        assert attestation.data.source == state.previous_justified_checkpoint

    shard = get_shard(state, attestation)
    shard_start_slot = get_next_slot_for_shard(state, shard)

    # Signature check
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
    # Type 1: on-time attestations
    if attestation.custody_bits_blocks != []:
        # Correct slot
        assert data.slot + MIN_ATTESTATION_INCLUSION_DELAY == state.slot
        # Correct data root count
        assert len(attestation.custody_bits_blocks) == len(get_offset_slots(state, shard_start_slot))
        # Correct parent block root
        assert data.beacon_block_root == get_block_root_at_slot(state, get_previous_slot(state.slot))
    # Type 2: no shard transition, no custody bits  # TODO: could only allow for older attestations.
    else:
        # assert state.slot - compute_start_slot_at_epoch(compute_epoch_at_slot(data.slot)) < SLOTS_PER_EPOCH
        assert data.shard_transition_root == Root()
```

###### `apply_shard_transition`

```python
def apply_shard_transition(state: BeaconState, shard: Shard, transition: ShardTransition) -> None:
    # Slot the attestation starts counting from
    start_slot = get_next_slot_for_shard(state, shard)

    # Correct data root count
    offset_slots = get_offset_slots(state, start_slot)
    assert (
        len(transition.shard_data_roots)
        == len(transition.shard_states)
        == len(transition.shard_block_lengths)
        == len(offset_slots)
    )
    assert transition.start_slot == start_slot

    # Reconstruct shard headers
    headers = []
    proposers = []
    shard_parent_root = state.shard_states[shard].latest_block_root
    for i in range(len(offset_slots)):
        if any(transition.shard_data_roots):
            headers.append(ShardSignableHeader(
                shard_parent_root=shard_parent_root,
                parent_hash=get_block_root_at_slot(state, get_previous_slot(state.slot)),
                slot=offset_slots[i],
                body_root=transition.shard_data_roots[i]
            ))
            proposers.append(get_shard_proposer_index(state, shard, offset_slots[i]))
            shard_parent_root = hash_tree_root(headers[-1])

    # Verify correct calculation of gas prices and slots
    prev_gasprice = state.shard_states[shard].gasprice
    for i in range(len(offset_slots)):
        shard_state = transition.shard_states[i]
        block_length = transition.shard_block_lengths[i]
        assert shard_state.gasprice == get_updated_gasprice(prev_gasprice, block_length)
        assert shard_state.slot == offset_slots[i]
        prev_gasprice = shard_state.gasprice

    pubkeys = [state.validators[proposer].pubkey for proposer in proposers]
    signing_roots = [
        compute_signing_root(header, get_domain(state, DOMAIN_SHARD_PROPOSAL, compute_epoch_at_slot(header.slot)))
        for header in headers
    ]
    # Verify combined proposer signature
    assert bls.AggregateVerify(zip(pubkeys, signing_roots), signature=transition.proposer_signature_aggregate)

    # Save updated state
    state.shard_states[shard] = transition.shard_states[-1]
    state.shard_states[shard].slot = state.slot - 1
```

###### `process_crosslink_for_shard`

```python
def process_crosslink_for_shard(state: BeaconState,
                                shard: Shard,
                                shard_transition: ShardTransition,
                                attestations: Sequence[Attestation]) -> Root:
    committee = get_beacon_committee(state, get_current_epoch(state), shard)
    online_indices = get_online_validator_indices(state)

    # Loop over all shard transition roots
    shard_transition_roots = set([a.data.shard_transition_root for a in attestations])
    for shard_transition_root in sorted(shard_transition_roots):
        transition_attestations = [a for a in attestations if a.data.shard_transition_root == shard_transition_root]
        transition_participants: Set[ValidatorIndex] = set()
        for attestation in transition_attestations:
            participants = get_attesting_indices(state, attestation.data, attestation.aggregation_bits)
            transition_participants = transition_participants.union(participants)

        enough_online_stake = (
            get_total_balance(state, online_indices.intersection(transition_participants)) * 3 >=
            get_total_balance(state, online_indices.intersection(committee)) * 2
        )
        # If not enough stake, try next transition root
        if not enough_online_stake:
            continue

        # Attestation <-> shard transition consistency
        assert shard_transition_root == hash_tree_root(shard_transition)
        assert attestation.data.head_shard_root == shard_transition.shard_data_roots[-1]

        # Apply transition
        apply_shard_transition(state, shard, shard_transition)
        # Apply proposer reward and cost
        beacon_proposer_index = get_beacon_proposer_index(state)
        estimated_attester_reward = sum([get_base_reward(state, attester) for attester in transition_participants])
        proposer_reward = Gwei(estimated_attester_reward // PROPOSER_REWARD_QUOTIENT)
        increase_balance(state, beacon_proposer_index, proposer_reward)
        states_slots_lengths = zip(
            shard_transition.shard_states,
            get_offset_slots(state, get_next_slot_for_shard(state, shard)),
            shard_transition.shard_block_lengths
        )
        for shard_state, slot, length in states_slots_lengths:
            proposer_index = get_shard_proposer_index(state, shard, slot)
            decrease_balance(state, proposer_index, shard_state.gasprice * length)

        # Return winning transition root
        return shard_transition_root

    # No winning transition root, ensure empty and return empty root
    assert shard_transition == ShardTransition()
    return Root()
```

###### `process_crosslinks`

```python
def process_crosslinks(state: BeaconState,
                       block_body: BeaconBlockBody,
                       attestations: Sequence[Attestation]) -> Set[Tuple[Shard, Root]]:
    winners: Set[Tuple[Shard, Root]] = set()
    committee_count = get_committee_count_at_slot(state, state.slot)
    for committee_index in map(CommitteeIndex, range(committee_count)):
        shard = compute_shard_from_committee_index(state, committee_index, state.slot)
        # All attestations in the block for this shard
        shard_attestations = [
            attestation for attestation in attestations
            if get_shard(state, attestation) == shard and attestation.data.slot == state.slot
        ]
        shard_transition = block_body.shard_transitions[shard]
        winning_root = process_crosslink_for_shard(state, shard, shard_transition, shard_attestations)
        if winning_root != Root():
            winners.add((shard, winning_root))
    return winners
```

###### `process_attestations`

```python
def process_attestations(state: BeaconState, block_body: BeaconBlockBody, attestations: Sequence[Attestation]) -> None:
    # Basic validation
    for attestation in attestations:
        validate_attestation(state, attestation)

    # Process crosslinks
    winners = process_crosslinks(state, block_body, attestations)

    # Store pending attestations for epoch processing
    for attestation in attestations:
        is_winning_transition = (get_shard(state, attestation), attestation.data.shard_transition_root) in winners
        pending_attestation = PendingAttestation(
            aggregation_bits=attestation.aggregation_bits,
            data=attestation.data,
            inclusion_delay=state.slot - attestation.data.slot,
            crosslink_success=is_winning_transition and attestation.data.slot == state.slot,
            proposer_index=get_beacon_proposer_index(state),
        )
        if attestation.data.target.epoch == get_current_epoch(state):
            state.current_epoch_attestations.append(pending_attestation)
        else:
            state.previous_epoch_attestations.append(pending_attestation)
```

##### New Attester slashing processing

```python
def get_indices_from_committee(
        committee: List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE],
        bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]) -> List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE]:
    assert len(bits) == len(committee)
    return List[ValidatorIndex, MAX_VALIDATORS_PER_COMMITTEE](
        [validator_index for i, validator_index in enumerate(committee) if bits[i]]
    )
```

```python
def process_attester_slashing(state: BeaconState, attester_slashing: AttesterSlashing) -> None:
    indexed_attestation_1 = attester_slashing.attestation_1
    indexed_attestation_2 = attester_slashing.attestation_2
    assert is_slashable_attestation_data(
        indexed_attestation_1.attestation.data,
        indexed_attestation_2.attestation.data,
    )
    assert is_valid_indexed_attestation(state, indexed_attestation_1)
    assert is_valid_indexed_attestation(state, indexed_attestation_2)

    indices_1 = get_indices_from_committee(
        indexed_attestation_1.committee,
        indexed_attestation_1.attestation.aggregation_bits,
    )
    indices_2 = get_indices_from_committee(
        indexed_attestation_2.committee,
        indexed_attestation_2.attestation.aggregation_bits,
    )

    slashed_any = False
    indices = set(indices_1).intersection(indices_2)
    for index in sorted(indices):
        if is_slashable_validator(state.validators[index], get_current_epoch(state)):
            slash_validator(state, index)
            slashed_any = True
    assert slashed_any
```

#### Shard transition false positives

```python
def verify_shard_transition_false_positives(state: BeaconState, block_body: BeaconBlockBody) -> None:
    # Verify that a `shard_transition` in a block is empty if an attestation was not processed for it
    for shard in range(get_active_shard_count(state)):
        if state.shard_states[shard].slot != state.slot - 1:
            assert block_body.shard_transitions[shard] == ShardTransition()
```

#### Light client processing

```python
def process_light_client_signatures(state: BeaconState, block_body: BeaconBlockBody) -> None:
    committee = get_light_client_committee(state, get_current_epoch(state))
    total_reward = Gwei(0)
    signer_pubkeys = []
    for bit_index, participant_index in enumerate(committee):
        if block_body.light_client_signature_bitfield[bit_index]:
            signer_pubkeys.append(state.validators[participant_index].pubkey)
            increase_balance(state, participant_index, get_base_reward(state, participant_index))
            total_reward += get_base_reward(state, participant_index)

    increase_balance(state, get_beacon_proposer_index(state), Gwei(total_reward // PROPOSER_REWARD_QUOTIENT))
    
    slot = get_previous_slot(state.slot)
    signing_root = compute_signing_root(get_block_root_at_slot(state, slot), 
                                        get_domain(state, DOMAIN_LIGHT_CLIENT, compute_epoch_at_slot(slot)))
    return bls.FastAggregateVerify(signer_pubkeys, signing_root, signature=block_body.light_client_signature)
```


### Epoch transition

This epoch transition overrides the phase0 epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    process_justification_and_finalization(state)
    process_rewards_and_penalties(state)
    process_registry_updates(state)
    process_reveal_deadlines(state)
    process_slashings(state)
    process_final_updates(state)
    process_custody_final_updates(state)
    process_online_tracking(state)
    process_light_client_committee_updates(state)
```

#### Custody game updates

`process_reveal_deadlines` and `process_custody_final_updates` are defined in [the Custody Game spec](./1_custody-game.md), 

#### Online-tracking

```python
def process_online_tracking(state: BeaconState) -> None:
    # Slowly remove validators from the "online" set if they do not show up
    for index in range(len(state.validators)):
        if state.online_countdown[index] != 0:
            state.online_countdown[index] = state.online_countdown[index] - 1

    # Process pending attestations
    for pending_attestation in state.current_epoch_attestations + state.previous_epoch_attestations:
        for index in get_attesting_indices(state, pending_attestation.data, pending_attestation.aggregation_bits):
            state.online_countdown[index] = ONLINE_PERIOD
```

#### Light client committee updates

```python
def process_light_client_committee_updates(state: BeaconState) -> None:
    # Update light client committees
    if get_current_epoch(state) % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
        state.current_light_committee = state.next_light_committee
        new_committee = get_light_client_committee(state, get_current_epoch(state) + LIGHT_CLIENT_COMMITTEE_PERIOD)
        state.next_light_committee = committee_to_compact_committee(state, new_committee)
```
