from eth2spec.gen_helpers.gen_from_tests.gen import run_state_test_generators
from eth2spec.phase0 import spec as spec_phase0
from eth2spec.lightclient_patch import spec as spec_lightclient_patch
from eth2spec.phase1 import spec as spec_phase1
from eth2spec.test.context import PHASE0, PHASE1, LIGHTCLIENT_PATCH


specs = (spec_phase0, spec_lightclient_patch, spec_phase1)


if __name__ == "__main__":
    phase_0_mods = {key: 'eth2spec.test.phase0.epoch_processing.test_process_' + key for key in [
        'justification_and_finalization',
        'rewards_and_penalties',
        'registry_updates',
        'slashings',
        'eth1_data_reset',
        'effective_balance_updates',
        'slashings_reset',
        'randao_mixes_reset',
        'historical_roots_update',
        'participation_record_updates',
    ]}
    lightclient_patch_mods = {
        **{key: 'eth2spec.test.lightclient_patch.epoch_processing.test_process_' + key for key in [
            'sync_committee_updates',
        ]},
        **phase_0_mods,
    }  # also run the previous phase 0 tests
    phase_1_mods = {**{key: 'eth2spec.test.phase1.epoch_processing.test_process_' + key for key in [
        'reveal_deadlines',
        'challenge_deadlines',
        'custody_final_updates',
    ]}, **phase_0_mods}  # also run the previous phase 0 tests (but against phase 1 spec)

    all_mods = {
        PHASE0: phase_0_mods,
        LIGHTCLIENT_PATCH: lightclient_patch_mods,
        PHASE1: phase_1_mods,
    }

    run_state_test_generators(runner_name="epoch_processing", specs=specs, all_mods=all_mods)
