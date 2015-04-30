mkdir -p logs
python3 -m dotainput.stream.start > logs/stream.log 2>&1 &
python3 -m telegram.processor > logs/processor.log 2>&1 &
