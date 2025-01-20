#!/bin/bash
echo "Installing Home Manager dbus bridge..."
# SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SCRIPT_DIR="/data/module_m"

# wait until dbus settings are active (when installing via blind install)
while [ $(dbus -y | grep -c "com.victronenergy.settings") == 0 ]; do
    logMessage "waiting for dBus settings"
    sleep 1
done

sleep 2

echo "Generate start and stop scripts.."
# Kill script
echo "#!/bin/bash" > "$SCRIPT_DIR/kill_me.sh"
echo "kill \$(pgrep -f \"python $SCRIPT_DIR/dbus-homemanager.py\")" >> "$SCRIPT_DIR"/kill_me.sh

# Run script
mkdir -p "$SCRIPT_DIR/service"
echo "#!/bin/bash" > "$SCRIPT_DIR/service/run"
echo "python3 $SCRIPT_DIR/dbus-homemanager.py >> $SCRIPT_DIR/dbus-homemanager.log 2>&1 &" >> "$SCRIPT_DIR/service/run"

echo "Marking files as executable.."
chmod +x "$SCRIPT_DIR/dbus-homemanager.py"
chmod +x "$SCRIPT_DIR/kill_me.sh"
chmod +x "$SCRIPT_DIR/service/run"

echo "Register service..."
ln -s "$SCRIPT_DIR/service" /service/venus-homemanager
if [ ! -f "/data/rc.local" ]; then
  # Create rc.local if not existing
  echo "#!/bin/bash" > /data/rc.local
  chmod +x /data/rc.local
fi

# check if rc.local already contains the service
if [ $(grep -c "ln -s $SCRIPT_DIR/service /service/venus-homemanager" /data/rc.local) -eq 0 ]; then
  echo "ln -s $SCRIPT_DIR/service /service/venus-homemanager" >> /data/rc.local
fi

echo "Installation finished!"