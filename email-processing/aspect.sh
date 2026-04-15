#!/usr/bin/env bash
(
    # -- calling: -- sudo -u email /home/email/aspect.sh
    source /home/mpoil/empoil/bin/activate
    rm -f /tmp/main_sftp
    # -------------------------- Variables -----------------------
    # SFTP
    export ENABLE_SFTP=False

    # SMTP variables
    export SMTP_SERVER=
    export SMTP_PORT=465
    export SMTP_SENDER_EMAIL=
    export SMTP_SENDER_PASSWORD=
    export EMAIL_DATABASE=/home/mpoil/.mail/zoho
    export LOG_FOLDER='/home/u/log/'
    export MARK_FOLDER='/home/u/' # folder with clients subfolders
    export CC_EMAIL=''


    CLIENTS_FILE="/home/mark/clients_distribution_list.csv"


    if [[ ! -f "$CLIENTS_FILE" ]]; then
	echo "Error: File $CLIENTS_FILE not found." | tee >(sed "s/^/$(date '+%Y-%m-%d %H:%M:%S') /") | tee -a "${LOG_FOLDER%/}/log.log"
	source send_telegram_notification.sh "Error: File $CLIENTS_FILE not found."
	exit 1
    fi

    # ------------------------ Get Emails ------------------
    # proxychains -f /home/email/proxychains.conf
    mbsync -V -c /home/mpoil/.config/isyncrc -a

    a=$(notmuch new 2>&1)

    echo $a | grep "No new mail."
    if [ $? -eq 0 ]; then
	echo "No new mail." | tee >(sed "s/^/$(date '+%Y-%m-%d %H:%M:%S') /") | tee -a "${LOG_FOLDER%/}/log.log"
	exit 0
    fi

    # notmuch tag --input=/home/mpoil/my.notmuch
    echo Tag all sent messages as sent and remove tags inbox and unread.
    notmuch tag +sent -new -inbox -unread -- folder:Sent

    echo Tag "tosftp" ICE Data emails that will be processed to USER_CURVE_YYYYMMDD.
    # notmuch tag -inbox +tosftp -- tag:inbox AND '( from:user@site.com OR from:user2@site.com )' AND '( subject:.*ICE Data.* OR subject:.*Prices.* )'
    notmuch tag -inbox -unread +tosftp -- tag:inbox AND '( from:user@site.com OR from:user2@site.com )' AND subject:'.*ICE Data.*'

    echo Tag "pricescopy" Prices emails that will just copied to user folder.
    notmuch tag -inbox -unread +pricescopy -- tag:inbox AND '( from:user@site.com OR from:user2@site.com )' AND subject:'.*Prices.*'

    echo Tag "bbr" Prices emails that will just copied to user folder.
    notmuch tag -inbox -unread +bbr -- tag:inbox AND '( from:user@site.com OR from:user2@site.com OR from:vitalij@gmx.com )' AND subject:'.*BBR. Big Big Report.*'

    echo '----------------------- Tag "pricescopy" main_attachments.py ----------------'
    export TAG_TO_PROCESS='pricescopy'
    export TARGET_FOLDER='/home/user/prices/'
    res=$(python3 /home/mpoil/aspect-mpoil/main_attachments.py)
    if [[ $(echo "$res" | tail -n 1 ) != "Success" ]]; then
	# echo "Exception occured BRR: $res" >> "${LOG_FOLDER%/}/log.log"
	echo "Exception in /home/mpoil/aspect-mpoil/main_attachments.py for pricescopy tag"
	source send_telegram_notification.sh "Exception in /home/mpoil/aspect-mpoil/main_attachments.py for pricescopy tag "
    fi
    # echo rsync -av --omit-dir-times --no-perms --ignore-existing "$TARGET_FOLDER" /home/TAP/curves/
    # rsync -av --omit-dir-times --no-perms --ignore-existing "$TARGET_FOLDER" /home/TAP/curves/
    echo '----------------------- Tag BBR ----------------'
    export TAG_TO_PROCESS='bbr'
    export TARGET_FOLDER='/home/user/BBR_files/'

    res=$(python3 /home/mpoil/aspect-mpoil/main_attachments.py)
    if [[ $(echo "$res" | tail -n 1 ) != "Success" ]]; then
	# echo "Exception occured BRR: $res" >> "${LOG_FOLDER%/}/log.log"
	echo "Exception in /home/mpoil/aspect-mpoil/main_attachments.py for BBR tag"
	source send_telegram_notification.sh "Exception in /home/mpoil/aspect-mpoil/main_attachments.py for BBR tag "
    fi
    # - table 'bbr'
    con='postgresql+asyncpg://powerbi:powerbi1@localhost:54432/mpoil'
    python3 /home/mpoil/aspect-mpoil/main_bbr.py --con $con --path $TARGET_FOLDER
    echo main_bbr.py $?
    echo rsync -av --omit-dir-times --no-perms --ignore-existing $TARGET_FOLDER /home/jup/Nuvo/
    rsync -av --omit-dir-times --no-perms --ignore-existing $TARGET_FOLDER /home/jup/Nuvo/

    echo " ----------------------- Read Clients -----------------"
    export TAG_TO_PROCESS='tosftp'
    # Set the Internal Field Separator to comma and read
    # && [[ -n "$client_name" ]]
    extract_email_part() {
	local email_part="$1"

	local input="${email_part%%@*}"
	# Use a regex to extract the part before '@'
	last_word=$(echo "$input" | awk '{print $NF}')
	echo "$last_word"
    }

    extract_folder() {
	# Remove trailing slash if present and get the last component
	local word="${1%/}"
	word="${word##*/}"
	echo "$word"
    }


    while IFS=',' read -r client_name folder_path email_address ; do
	# Trim whitespace from each field
	client_name="${client_name## }"; client_name="${client_name%% }"
	folder_path="${folder_path## }"; folder_path="${folder_path%% }"
	email_address="${email_address## }"; email_address="${email_address%% }"
	# echo -- $client_name $folder_path $email_address

	uname=$(basename "$folder_path")
	if [ -z "$uname" ]; then
            uname="$client_name"
	fi
	if [[ -z "$unmae" && ! -z "$folder_path" ]]; then
            uname=$(extract_folder "$folder_path")
	fi
	# if [ -z "$uname" && ! -z "$email_address" ]; then
	#     uname=$(extract_email_part "$email_address")
	# fi
	if [ -z "$uname" ]; then
            continue
	fi
	if [ -z "$client_name" ]; then
            client_name=$uname
	fi
	# Process each line
	echo "Client Name: $client_name"
	echo "Folder Path: $folder_path"
	echo "Email Address: $email_address"


	# - Create SFTP user
	# if true ; then
	if [[ ! -z "$folder_path" && ! -d "$folder_path" ]]; then
	    usname=$(basename "$folder_path")
	    echo "Creating user \"$usname\""
	    # pass=$(gpg --gen-random --armor 1 100 | head -c 10)
	    pass=$username
	    res=$(sudo /home/mpoil/aspect-mpoil/create_sftpuser.sh "$usname" "$pass")
	    resv=$?
	    echo "$res" | grep 'User successfully created'
	    if [[ $? -ne 0 || $resv -ne 0 ]] ; then
		source send_telegram_notification.sh "Failed to create user $usname"
		exit 1
	    else
		source send_telegram_notification.sh "SFTP://aspect.site.com User created, login:${usname}, password: ${pass}"
	    fi
	fi
	# - create /home/user/clients/XXX folder
	export CLIENT_NAME="$client_name"
	export CLIENT_EMAIL="$email_address"
	export CLIENT_FOLDER="${USER_FOLDER%/}/clients/${client_name}" # outgoing files
	export LOOKUP_TABLE="${USER_FOLDER%/}/clients/price_lookup_${client_name}.xlsx"
	mkdir -p "$CLIENT_FOLDER"
	if [[ ! -e "$LOOKUP_TABLE" ]]; then
            source send_telegram_notification.sh "Lookup table doesn't exist, please create \"$LOOKUP_TABLE\" file. Can't proceed ICE Data file."
            continue
	fi

	# - process "tosftp" emails
	# always return error code
	echo python3 /home/mpoil/aspect-mpoil/main_curve.py
	res=$(python3 /home/mpoil/aspect-mpoil/main_curve.py)
	if [[ "$res" != "No new emails." && "$res" != "Success" ]]; then
            # echo "Exception in main_curve.py: $res" >> "${LOG_FOLDER%/}/log.log"
            echo "Exception in main_curve.py: $res"
            source send_telegram_notification.sh "Exception in /home/mpoil/aspect-mpoil/main_curve.py for $client_name $email_address"
            exit 1
	else
            echo "$res"
	fi

	# - copy to sftp folder of client
	if [[ -d "$CLIENT_FOLDER" && -d "$folder_path" ]]; then
            sudo rsync -v --ignore-existing "$CLIENT_FOLDER" "$folder_path"/curves/
	fi
	echo -e "--- client processed\n"
    done < "$CLIENTS_FILE"

    notmuch tag -tosftp +processed -- tag:tosftp
)
# if [ $? -eq 0 ]; then
#     echo Success, notmuch tag -tosftp +processed -- tag:tosftp
#     notmuch tag -tosftp +processed -- tag:tosftp
# fi
# if [[ "$res" != "No new emails." ]]; then
#     # export USER_FOLDER='/tmp/'
#     # export CLIENT_NAME="user"
#     # export CLIENT_EMAIL="user@site.com"
#     # python3 /home/mpoil/aspect-mpoil/main_curve.py
# fi


# if [ -n "$files" ];then
# - put bbr reports to "mpoil" database to table "bbr"
# fi
# ------------------------- Tag Emacs Processed ------------------
# tail -n1 "${LOG_FOLDER%/}/log.log" | grep Success
# if [ $? -eq 0 ]; then
#     echo Success, notmuch tag -tosftp +processed -- tag:tosftp
#     notmuch tag -tosftp +processed -- tag:tosftp
#     # echo sshpass
# #     # proxychains -q -f /home/mpoil/proxychains.conf
# #     sshpass -p $SFTP_PASSWORD sftp -P $SFTP_PORT ${SFTP_USERNAME}@${SFTP_HOSTNAME} <<- EOF
# #     put /home/mpoil/log/log.log
# #     exit
# # EOF
# fi
