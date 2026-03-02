# RemoteEnvMeasure.py
# Drop into: /home/licor/apps/dynamic/RemoteEnvMeasure.py  (or any /home/licor/apps subfolder)

from bpdefs import (
    EXEC, ASSIGN, IF, ELSE, RETURN, WHILE, WAIT, SETCONTROL, SHOW, LOG,
    DataDict
)

steps = [
    # Python helpers available to EXEC / WAIT(event=...) expressions
    EXEC(0, source="import os, json, time"),

    # Where the "tell it to measure" command arrives, and where we write an ack
    ASSIGN("cmd_path", exp="'/home/licor/apps/dynamic/remote_cmd.json'"),
    ASSIGN("ack_path", exp="'/home/licor/apps/dynamic/remote_ack.json'"),

    # Defaults if your JSON doesn't specify them
    ASSIGN("default_wait_s", exp="10"),
    ASSIGN("default_co2_tol", exp="20"),

    # Track a few measured values for optional waits / acknowledgements
    ASSIGN("co2r_meas", dd=DataDict("CO2_r", "Meas"), track=True),
    ASSIGN("co2s_meas", dd=DataDict("CO2_s", "Meas"), track=True),
    ASSIGN("tch_meas",  dd=DataDict("Tchamber", "Meas"), track=True),
    ASSIGN("ppfd_in",   dd=DataDict("PPFD_in", "Meas"), track=True),

    SHOW(string="'RemoteEnvMeasure running. Waiting for command file: {}'.format(cmd_path)"),

    # Main loop: wait for a command file, execute it, repeat forever.
    WHILE("True", steps=(

        # Block here until you drop remote_cmd.json onto the instrument
        WAIT(event="os.path.exists(cmd_path)"),

        # Read JSON + delete command file so the next command can arrive
        EXEC(0, source=
            "cmd=None\n"
            "try:\n"
            "  with open(cmd_path,'r') as f:\n"
            "    cmd=json.load(f)\n"
            "except Exception as e:\n"
            "  cmd={'action':'error','error':str(e)}\n"
            "try:\n"
            "  os.remove(cmd_path)\n"
            "except Exception:\n"
            "  pass\n"
        ),

        SHOW(string="'CMD: {}'.format(cmd)"),

        # Allow remote stop
        IF("str(cmd.get('action','')).lower() in ('stop','quit','exit')", steps=(
            SHOW(string="'Stopping RemoteEnvMeasure.'"),
            RETURN(),
        )),

        # --- Apply setpoints (only if present in cmd) ---
        # Accepted keys: co2_r, qin, flow, tair, rh_air, fan_rpm, pressure
        ASSIGN("sp_co2", exp="cmd.get('co2_r', None)"),
        IF("sp_co2 is not None", steps=(
            SETCONTROL("CO2_r", "sp_co2", "float"),  # reference CO2 setpoint
        )),

        ASSIGN("sp_qin", exp="cmd.get('qin', None)"),
        IF("sp_qin is not None", steps=(
            SETCONTROL("Qin", "sp_qin", "float"),    # light incident on leaf
        )),

        ASSIGN("sp_flow", exp="cmd.get('flow', None)"),
        IF("sp_flow is not None", steps=(
            SETCONTROL("Flow", "sp_flow", "float"),  # flow to chamber
        )),

        ASSIGN("sp_tair", exp="cmd.get('tair', None)"),
        IF("sp_tair is not None", steps=(
            SETCONTROL("Tair", "sp_tair", "float"),  # chamber air temperature
        )),

        ASSIGN("sp_rh", exp="cmd.get('rh_air', None)"),
        IF("sp_rh is not None", steps=(
            SETCONTROL("RH_air", "sp_rh", "float"),  # chamber RH setpoint
        )),

        ASSIGN("sp_fan", exp="cmd.get('fan_rpm', None)"),
        IF("sp_fan is not None", steps=(
            SETCONTROL("Fan_rpm", "sp_fan", "float"),  # fan rpm setpoint
        )),

        ASSIGN("sp_p", exp="cmd.get('pressure', None)"),
        IF("sp_p is not None", steps=(
            SETCONTROL("Pressure", "sp_p", "float"),   # chamber over-pressure
        )),

        # Optional: wait for CO2_r to come within tolerance (default 20 ppm)
        ASSIGN("co2_tol", exp="cmd.get('co2_tol', default_co2_tol)"),
        IF("sp_co2 is not None and cmd.get('wait_for_co2', True)", steps=(
            SHOW(string="'Waiting for CO2_r to reach target (±{} ppm)...'.format(co2_tol)"),
            WAIT(event="abs(co2r_meas - sp_co2) < co2_tol"),
        )),

        # Optional: additional fixed wait
        ASSIGN("wait_s", exp="cmd.get('wait_s', default_wait_s)"),
        IF("wait_s and wait_s > 0", steps=(
            SHOW(string="'Extra wait: {} s'.format(wait_s)"),
            WAIT(dur="wait_s", units="Seconds"),
        )),

        # Trigger a “measurement” = log a record (requires log file open)
        IF("cmd.get('log', True)", steps=(
            SHOW(string="'Logging one record (LOG())...'"),
            LOG(),
        )),

        # Write an acknowledgement you can fetch back over scp/sftp
        EXEC(0, source=
            "ack={\n"
            " 'ts': time.time(),\n"
            " 'cmd': cmd,\n"
            " 'meas': {\n"
            "   'CO2_r': co2r_meas,\n"
            "   'CO2_s': co2s_meas,\n"
            "   'Tchamber': tch_meas,\n"
            "   'PPFD_in': ppfd_in,\n"
            " }\n"
            "}\n"
            "with open(ack_path,'w') as f:\n"
            "  f.write(json.dumps(ack, indent=2))\n"
        ),

        SHOW(string="'Done. Waiting for next command.'"),
    )),
]