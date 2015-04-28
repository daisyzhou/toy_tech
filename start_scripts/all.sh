mkdir -p logs
python3 -m dotainput.stream.start > logs/stream.log
python3 -m telegram.processor > logs/processor.log
