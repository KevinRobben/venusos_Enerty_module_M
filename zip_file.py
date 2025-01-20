import tarfile
import os

def create_tgz(folder_name, output_name):
    """
    Creates a .tgz archive from the contents of a folder.
    
    :param folder_name: Name of the folder whose contents will be archived
    :param output_name: Name of the output .tgz file
    """
    if not os.path.isdir(folder_name):
        print(f"Error: Folder '{folder_name}' does not exist.")
        return

    with tarfile.open(output_name, "w:gz") as tar:
        # Add each item in the folder to the archive
        for item in os.listdir(folder_name):
            item_path = os.path.join(folder_name, item)
            tar.add(item_path, arcname=item)  # Use the item name only
    print(f"'{output_name}' has been created successfully.")

# Define the folder and output file name
folder_to_zip = "venus-data"
output_tgz_file = "venus-data.tgz"

# Create the .tgz file
create_tgz(folder_to_zip, output_tgz_file)
