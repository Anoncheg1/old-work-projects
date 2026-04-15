#!/usr/bin/env bash

export LOG_FOLDER='/home/mpoil/log/'

send_telegram_notification() {
    local filename="${LOG_FOLDER%/}/telegram-output.log"
    TOKEN=xxxx
    CHAT_ID=-4
    local MESSAGE="$@"

    if [ ! -f "$filename" ]; then
        touch "$filename"
    fi
    # Get the last line of the file
    local last_line=$(tail -n 1 "$filename")

    # Compare the last line with the new string
    if [ "$last_line" != "$MESSAGE" ]; then

        echo "$MESSAGE" >> "$filename"
        echo "$MESSAGE" # to STDOUT

        echo "$MESSAGE" >> "${LOG_FOLDER%/}/log.log"
	echo
        curl_response=$(curl -A mozilla -s -X POST "https://api.telegram.org/bot$TOKEN/sendMessage" -d "chat_id=$CHAT_ID" -d "text=$MESSAGE" 2>&1)
	if [ $? -ne 0 ]; then
	    echo "Curl failed. Error:"
	    echo "$curl_response"
	    return 1
	fi

	echo "$curl_response" | grep '"ok":true' > /dev/null
	if [ $? -ne 0 ]; then
	    echo "Error in cRUL to telegram response in send_telegram_notification.sh :" "$curl_response"
	    return 1
	fi
    fi
}

if [ -z "$1" ]; then echo No input; return 1 ; fi

send_telegram_notification $@
