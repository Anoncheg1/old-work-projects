CLIENTS_FILE="/home/mark/clients_distribution_list.csv"

source /home/webforms/formsenv/bin/activate

while IFS=',' read -r client_name folder_path email_address ; do
    # Trim whitespace from each field
    client_name="${client_name## }"; client_name="${client_name%% }"
    folder_path="${folder_path## }"; folder_path="${folder_path%% }"
    email_address="${email_address## }"; email_address="${email_address%% }"

    uname=$(basename "$folder_path")
    if [ -z "$uname" ]; then
        uname="$client_name"
    fi
    if [ -z "$uname" ]; then
        uname=$(extract_email_part "$email_address")
    fi
    if [ -z "$uname" ]; then
        continue
    fi
    if [ -z "$client_name" ]; then
        client_name=$uname
    fi
    echo python3 change_user.py "$client_name" "$client_name"
    python3 change_user.py "$client_name" "$client_name"

done < "$CLIENTS_FILE"
