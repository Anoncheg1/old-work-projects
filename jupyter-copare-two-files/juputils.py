import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import re
import os
import tempfile
import ipywidgets as widgets
from IPython.display import display
import calendar
# own
from utils import create_row_iterator


# ----------- ipywidgets select two wiles ---------------
f1path = None
f2path = None
novu_folder = "/home/jup/Nuvo/"


def create_file_selector(folder_path, description):
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    select = widgets.Select(options=files, description=description, rows=10)
    upload = widgets.FileUpload(accept='', multiple=False, description=f'Upload {description}')
    return widgets.VBox([select, upload]), select, upload

def save_uploaded_file(uploaded_file):
    with tempfile.NamedTemporaryFile(mode='wb', delete=False, dir='/tmp', suffix=f'_{uploaded_file.name}') as temp_file:
        temp_file.write(uploaded_file.content)
    return temp_file.name

def get_file_path(folder_path, select, upload):
    if upload.value:
        # Handle the tuple structure of upload.value
        uploaded_file = next(iter(upload.value))
        return save_uploaded_file(uploaded_file)
    elif select.value:
        return os.path.join(folder_path, select.value)
    return "No file selected or uploaded"

def select_or_upload_novu_files():
    widget1, select1, upload1 = create_file_selector(novu_folder, "File 1:")
    widget2, select2, upload2 = create_file_selector(novu_folder, "File 2:")

    output = widgets.Output()

    def on_change(change):
        global f1path, f2path
        with output:
            output.clear_output()
            f1path=get_file_path(novu_folder, select1, upload1)
            f2path=get_file_path(novu_folder, select2, upload2)
            print(f"File 1: {f1path}")
            print(f"File 2: {f2path}")

    for w in (select1, upload1, select2, upload2):
        w.observe(on_change, names='value')

    display(widgets.HBox([widget1, widget2]))
    display(output)


# ---------------------------------------------------------------------------

def selected_object_to_numeric(df):
    "Fix types in df"
    # nc = df.select_dtypes(include=[np.number]).columns
    cc = df.select_dtypes(exclude=[np.number]).columns

    numeric_columns = []
    non_numeric_columns = []
    df2 = df.copy()
    for col in cc:
        # Replace empty strings with NaN
        df2[col] = df2[col].replace(r'^\s*$', np.nan, regex=True)

        # Attempt to convert to numeric
        converted = pd.to_numeric(df2[col], errors='coerce')

        # Check if any non-NaN values were introduced by the conversion
        if converted.isna().equals(df2[col].isna()):
            numeric_columns.append(col)
        else:
            non_numeric_columns.append(col)

    df[numeric_columns] = df[numeric_columns].apply(lambda x: pd.to_numeric(x, errors='coerce'))


def file_to_dataframe(path:str) -> pd.DataFrame:
    # file_path1 = '/home/mark/Nuvo/BBR. Big Big Report 2025-02-10 0711 at myaspect.net.xls'
    rows1 = list(create_row_iterator(path))
    # print(rows1[3][rows1[0].index('entrydate')])
    df = pd.DataFrame(rows1[1:], columns=rows1[0])
    # - prepare
    selected_object_to_numeric(df)
    # - fix dates
    if path.lower().endswith("xls"):
        dcols = df.columns.str.lower().str.contains('date')
        for co in df.columns[dcols]:
            vv = pd.to_numeric(df[co], errors='coerce')
            df[co] = pd.to_datetime(vv, unit='D', origin='1899-12-30')
    return df


def read_uploads(file1: bytes | str, file2: bytes | str) -> (pd.DataFrame, pd.DataFrame, pd.DataFrame):
    "file1 - bytes of file or string"
    if not isinstance(file1, str):
        # - Read uploads
        with tempfile.NamedTemporaryFile(mode='wb', delete=True) as temp_file:
            temp_file.write(file1)
            file1 = temp_file.name

    if not isinstance(file1, str):
        with tempfile.NamedTemporaryFile(mode='wb', delete=True) as temp_file:
            temp_file.write(file2)
            file2= temp_file.name

    df1 = file_to_dataframe(file1)
    df2 = file_to_dataframe(file2)
    # - Prepare dataframes, concat
    df1['left_right'] = 0
    df2['left_right'] = 1

    df = pd.concat([df1, df2], ignore_index=True)
    df1.drop('left_right', axis=1, inplace=True)
    df2.drop('left_right', axis=1, inplace=True)
    return df1, df2, df


def histogram_multiple(df, feature_mains, feature_binary, bins=20,
                       density=True, label_left='left', label_right='right',
                       image_save=None):
    """
    Plot multiple histograms in one figure for different feature_main parameters
    :param df: DataFrame
    :param feature_mains: List of continuous features
    :param feature_binary: Binary feature [0,1]
    :param bins: Number of bins for histograms
    :param density: Whether to normalize the histogram
    :param image_save: Path to save the image
    """
    n_plots = len(feature_mains)
    cols = min(3, n_plots)  # Max 3 columns
    rows = math.ceil(n_plots / cols)

    fig, axs = plt.subplots(rows, cols, figsize=(6*cols, 4*rows))
    fig.suptitle(f"Histograms for multiple features by {feature_binary}", fontsize=16)

    if n_plots == 1:
        axs = [axs]
    else:
        axs = axs.flatten()

    for i, feature_main in enumerate(feature_mains):
        ax = axs[i]
        df_1 = df[df[feature_binary] == 1][feature_main]
        df_0 = df[df[feature_binary] == 0][feature_main]

        df_0.hist(ax=ax, bins=bins, color='red', alpha=0.6, density=density, label=label_left)
        df_1.hist(ax=ax, bins=bins, color='green', alpha=0.6, density=density, label=label_right)

        ax.set_title(f"{feature_main}")
        ax.legend()
        ax.set_xlabel(feature_main)
        ax.set_ylabel('Density' if density else 'Count')
    # Remove any unused subplots
    for j in range(i+1, len(axs)):
        fig.delaxes(axs[j])

    plt.tight_layout()
    if image_save:
        plt.savefig(image_save)
    else:
        plt.show()

def prepare_label(string, max_length=20):
    """
    Prepare a string label for plotting by shortening it if it's too long.

    :param string: The input string to be prepared
    :param max_length: Maximum allowed length of the string (default 20)
    :return: The prepared string
    """
    if len(string) <= max_length:
        return string
    else:
        keep = (max_length - 3) // 2
        return f"{string[:keep]}...{string[-keep:]}"

def plot_top_n_by_binary(df, string_columns, binary_column, n=5, image_save=None,
                         label_left='left', label_right='right'):
    """
    Plot top N values for multiple string columns split by a binary column.

    :param df: pandas DataFrame
    :param string_columns: list of string column names
    :param binary_column: name of the binary column
    :param n: number of top values to plot (default 5)
    :param image_save: path to save the image (if None, the plot will be shown)
    """

    figsize = (15, 5*len(string_columns))

    def get_top_n_counts(data):
        return data.value_counts().nlargest(n)

    fig, axes = plt.subplots(len(string_columns), 1, figsize=figsize)
    if len(string_columns) == 1:
        axes = [axes]

    width = 0.35

    for idx, string_column in enumerate(string_columns):
        dfc = df[df[string_column].str.strip() != '']
        size1 = dfc[dfc[binary_column] == 0][string_column].unique().size
        size2 = dfc[dfc[binary_column] == 1][string_column].unique().size
        x = range(min(n, size1, size2))
        counts_0 = get_top_n_counts(dfc[dfc[binary_column] == 0][string_column])
        counts_1 = get_top_n_counts(dfc[dfc[binary_column] == 1][string_column])

        try:

            ax = axes[idx]

            ax.bar([i - width/2 for i in x], counts_0.values, width, label=label_left, color='skyblue')
            ax.bar([i + width/2 for i in x], counts_1.values, width, label=label_right, color='lightgreen')

            ax.set_ylabel('Count')
            ax.set_title(f'{string_column} ' + (f' - top {n}' if idx == 0 else '') )
            ax.set_xticks(x)

            # Apply prepare_label function to x-axis labels
            prepared_labels = [prepare_label(str(label)) for label in counts_0.index]
            ax.set_xticklabels(prepared_labels, rotation=45, ha='right', fontsize=8)

            ax.legend()

            for i, v in enumerate(counts_0.values):
                ax.text(i - width/2, v, str(v), ha='center', va='bottom')
            for i, v in enumerate(counts_1.values):
                ax.text(i + width/2, v, str(v), ha='center', va='bottom')
        except ValueError as e:
            print(f"Unable to create diagram for columnt {string_column}")
            continue

    plt.tight_layout()
    if image_save:
        plt.savefig(image_save)
    else:
        plt.show()


def cut_non_digit_underscore_hyphen(input_string):
    return re.sub(r'[^\d_-]', '', input_string)


# original_string = "Hello123_world-456!@#"
# result = cut_non_digit_underscore_hyphen(original_string)
# print(result)  # Output: 123_-456





def prepare_label(label, max_length=20):
    return str(label)[:max_length] + '...' if len(str(label)) > max_length else str(label)

from scipy.stats import gaussian_kde

def plot_numeric_differences(data1, data2, col, bins=20, density=True):
    plt.figure(figsize=(12, 6))

    # Remove inf and nan values
    data1 = data1[np.isfinite(data1)]
    data2 = data2[np.isfinite(data2)]

    # Calculate the range for both datasets
    min_val = min(data1.min(), data2.min())
    max_val = max(data1.max(), data2.max())

    # Create histogram bins
    bin_edges = np.linspace(min_val, max_val, bins + 1)

    # Plot histograms
    plt.hist(data1, bins=bin_edges, color='skyblue', alpha=0.4, density=density, label='df1')
    plt.hist(data2, bins=bin_edges, color='coral', alpha=0.4, density=density, label='df2')

    # Add KDE (similar to sns.histplot with kde=True)
    if density and len(data1) > 0 and len(data2) > 0:
        x_range = np.linspace(min_val, max_val, 300)
        if len(data1) > 1:
            kde1 = gaussian_kde(data1)
            plt.plot(x_range, kde1(x_range), color='blue', linewidth=2)
        if len(data2) > 1:
            kde2 = gaussian_kde(data2)
            plt.plot(x_range, kde2(x_range), color='darkred', linewidth=2)

    plt.title(f"Distribution of differences in {col}")
    plt.xlabel("Value")
    plt.ylabel("Density" if density else "Count")
    plt.legend()

    # Adjust y-axis to show the full height of the histogram bars
    plt.ylim(bottom=0)

    plt.tight_layout()

def plot_categorical_differences(data1, data2, col):
    top_5_1 = data1.value_counts().nlargest(5)
    top_5_2 = data2.value_counts().nlargest(5)

    plt.figure(figsize=(12, 6))

    # Get the union of top 5 categories from both datasets
    all_categories = list(set(top_5_1.index) | set(top_5_2.index))
    all_categories.sort()  # Sort for consistent ordering
    x = range(len(all_categories))
    width = 0.35

    # Prepare data for plotting
    values_1 = [top_5_1.get(cat, 0) for cat in all_categories]
    values_2 = [top_5_2.get(cat, 0) for cat in all_categories]

    plt.bar([i - width/2 for i in x], values_1, width, label='df1', color='skyblue', alpha=0.6)
    plt.bar([i + width/2 for i in x], values_2, width, label='df2', color='red', alpha=0.6)

    plt.title(f"Top values with differences in {col}")
    plt.xlabel("Value")
    plt.ylabel("Count")
    plt.xticks(x, [prepare_label(label) for label in all_categories], rotation=45, ha='right')

    for i, v in enumerate(values_1):
        if v > 0:
            plt.text(i - width/2, v, str(v), ha='center', va='bottom')
    for i, v in enumerate(values_2):
        if v > 0:
            plt.text(i + width/2, v, str(v), ha='center', va='bottom')

    plt.legend()
    plt.tight_layout()


def plot_date_differences(data1, data2, col):
    # Convert string dates to datetime
    data1 = pd.to_datetime(data1, errors='coerce')
    data2 = pd.to_datetime(data2, errors='coerce')

    # Group by month and count
    counts1 = data1.groupby(data1.dt.to_period('M')).size().reset_index(name='count')
    counts2 = data2.groupby(data2.dt.to_period('M')).size().reset_index(name='count')

    # Rename the period column to a common name for merging
    counts1 = counts1.rename(columns={counts1.columns[0]: 'period'})
    counts2 = counts2.rename(columns={counts2.columns[0]: 'period'})

    # Merge the two datasets
    merged = pd.merge(counts1, counts2, on='period', how='outer', suffixes=('_1', '_2')).fillna(0)

    # Convert period to string for plotting
    merged['month'] = merged['period'].astype(str)
    merged = merged.sort_values('period')

    # Prepare data for plotting
    months = merged['month']
    counts1 = merged['count_1']
    counts2 = merged['count_2']

    # Create the plot
    plt.figure(figsize=(15, 6))

    x = range(len(months))
    width = 0.35

    plt.bar([i - width/2 for i in x], counts1, width, label='df1', color='skyblue')
    plt.bar([i + width/2 for i in x], counts2, width, label='df2', color='red')

    plt.xlabel('Month')
    plt.ylabel('Count')
    plt.title(f'Comparison of {col} by Month')
    plt.xticks(x, months, rotation=45, ha='right')
    plt.legend()

    # Add value labels on the bars
    for i, v in enumerate(counts1):
        plt.text(i - width/2, v, str(int(v)), ha='center', va='bottom')
    for i, v in enumerate(counts2):
        plt.text(i + width/2, v, str(int(v)), ha='center', va='bottom')

    plt.tight_layout()
    plt.show()

def visualize_differences(merged, diff_columns):
    for col in diff_columns:
        diff_mask = merged[f'diff_{col}'] == True
        data1 = merged.loc[diff_mask, f'{col}_1']
        data2 = merged.loc[diff_mask, f'{col}_2']

        if 'date' in col.lower():
            plot_date_differences(data1, data2, col)
            continue


        # Check if the column can be converted to numeric
        try:
            data1 = pd.to_numeric(data1, errors='raise')
            data2 = pd.to_numeric(data2, errors='raise')
            is_numeric = True
        except (ValueError, TypeError):
            is_numeric = False
        if is_numeric and (data1.nunique() > 5 or data2.nunique() > 5):
            plot_numeric_differences(data1, data2, col)
        else:
            plot_categorical_differences(data1, data2, col)

        plt.tight_layout()
        plt.show()


def compare_columns(row, col):
    val1 = row[f'{col}_1']
    val2 = row[f'{col}_2']
    if pd.isna(val1) and pd.isna(val2):
        return np.nan
    elif pd.isna(val1) or pd.isna(val2):
        return True
    else:
        return val1 != val2

def identify_differences(df1, df2):
    "TODO: replace 'item' and 'tradeID'"
    df1['composite_key'] = df1['item'].astype(str) + '_' + df1['tradeID'].astype(str)
    df2['composite_key'] = df2['item'].astype(str) + '_' + df2['tradeID'].astype(str)

    # 2. Merge the DataFrames
    merged = df1.merge(df2, on='composite_key', how='outer', suffixes=('_1', '_2'))
    df1.drop('composite_key', axis=1, inplace=True)
    df2.drop('composite_key', axis=1, inplace=True)

    diff_columns = [col for col in df1.columns if col not in ['item', 'tradeID', 'composite_key'] and col not in merged.columns]

    for col in diff_columns:
        merged[f'diff_{col}'] = merged.apply(lambda row: compare_columns(row, col), axis=1)
    return merged
