"""
Plot test results from Kafka performance tests.

This module provides visualization functions similar to the original plot.py.
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


def setup_plotting_style():
    """Setup matplotlib and seaborn styling."""
    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=1.1)
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['xtick.labelsize'] = 10
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10


def plot_throughput_vs_latency(df: pd.DataFrame, 
                               x_col: str = 'mb_per_sec',
                               y_col: str = 'avg_latency_ms',
                               hue_col: Optional[str] = None,
                               title: str = 'Throughput vs Latency',
                               output_path: Optional[str] = None) -> plt.Figure:
    """
    Plot throughput vs latency scatter plot.
    
    Args:
        df: DataFrame with test metrics
        x_col: Column for x-axis (throughput)
        y_col: Column for y-axis (latency)
        hue_col: Column for color grouping
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    fig, ax = plt.subplots()
    
    if hue_col and hue_col in df.columns:
        sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax, s=100)
    else:
        sns.scatterplot(data=df, x=x_col, y=y_col, ax=ax, s=100)
    
    ax.set_xlabel('Throughput (MB/sec)')
    ax.set_ylabel('Latency (ms)')
    ax.set_title(title)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def plot_latency_percentiles(df: pd.DataFrame,
                             x_col: str = 'cluster_throughput_mb_per_sec',
                             title: str = 'Latency Percentiles vs Throughput',
                             output_path: Optional[str] = None) -> plt.Figure:
    """
    Plot latency percentiles (p50, p99) vs throughput.
    
    Args:
        df: DataFrame with test metrics
        x_col: Column for x-axis (throughput configuration)
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    fig, ax = plt.subplots()
    
    # Group by throughput and calculate mean latencies
    if x_col in df.columns:
        grouped = df.groupby(x_col).agg({
            'p50_latency_ms': 'mean',
            'p99_latency_ms': 'mean',
            'avg_latency_ms': 'mean'
        }).reset_index()
        
        ax.plot(grouped[x_col], grouped['avg_latency_ms'], 
               marker='o', label='Avg Latency', linewidth=2)
        ax.plot(grouped[x_col], grouped['p50_latency_ms'], 
               marker='s', label='P50 Latency', linewidth=2)
        ax.plot(grouped[x_col], grouped['p99_latency_ms'], 
               marker='^', label='P99 Latency', linewidth=2)
        
        ax.set_xlabel('Configured Throughput (MB/sec)')
        ax.set_ylabel('Latency (ms)')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def plot_throughput_efficiency(df: pd.DataFrame,
                               x_col: str = 'cluster_throughput_mb_per_sec',
                               y_col: str = 'sent_div_requested_mb_per_sec',
                               title: str = 'Throughput Efficiency',
                               output_path: Optional[str] = None) -> plt.Figure:
    """
    Plot actual vs requested throughput ratio.
    
    Args:
        df: DataFrame with test metrics
        x_col: Column for x-axis
        y_col: Column for y-axis (efficiency ratio)
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    fig, ax = plt.subplots()
    
    if x_col in df.columns and y_col in df.columns:
        grouped = df.groupby(x_col)[y_col].agg(['mean', 'std']).reset_index()
        
        ax.plot(grouped[x_col], grouped['mean'], 
               marker='o', linewidth=2, label='Mean Efficiency')
        ax.fill_between(
            grouped[x_col],
            grouped['mean'] - grouped['std'],
            grouped['mean'] + grouped['std'],
            alpha=0.3, label='±1 Std Dev'
        )
        
        # Add reference line at 1.0 (100% efficiency)
        ax.axhline(y=1.0, color='r', linestyle='--', alpha=0.5, label='100% Efficiency')
        
        ax.set_xlabel('Configured Throughput (MB/sec)')
        ax.set_ylabel('Actual / Requested Throughput Ratio')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_ylim(bottom=0)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def plot_consumer_throughput(df: pd.DataFrame,
                            x_col: str = 'cluster_throughput_mb_per_sec',
                            y_col: str = 'mb_per_sec',
                            group_col: Optional[str] = 'consumer_groups.num_groups',
                            title: str = 'Consumer Throughput',
                            output_path: Optional[str] = None) -> plt.Figure:
    """
    Plot consumer throughput by consumer group configuration.
    
    Args:
        df: DataFrame with consumer metrics
        x_col: Column for x-axis
        y_col: Column for y-axis (consumer throughput)
        group_col: Column for grouping (e.g., number of consumer groups)
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    fig, ax = plt.subplots()
    
    if group_col and group_col in df.columns:
        for group_value in df[group_col].unique():
            subset = df[df[group_col] == group_value]
            if x_col in subset.columns:
                grouped = subset.groupby(x_col)[y_col].mean().reset_index()
                ax.plot(grouped[x_col], grouped[y_col], 
                       marker='o', label=f'{group_col}={group_value}', linewidth=2)
    else:
        if x_col in df.columns:
            grouped = df.groupby(x_col)[y_col].mean().reset_index()
            ax.plot(grouped[x_col], grouped[y_col], marker='o', linewidth=2)
    
    ax.set_xlabel('Configured Throughput (MB/sec)')
    ax.set_ylabel('Consumer Throughput (MB/sec)')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def plot_grid(df: pd.DataFrame,
             x_col: str = 'cluster_throughput_mb_per_sec',
             y_col: str = 'avg_latency_ms',
             row_col: Optional[str] = None,
             col_col: Optional[str] = None,
             hue_col: Optional[str] = None,
             title: str = 'Performance Metrics Grid',
             output_path: Optional[str] = None) -> plt.Figure:
    """
    Create a grid of plots for different parameter combinations.
    
    Args:
        df: DataFrame with test metrics
        x_col: Column for x-axis
        y_col: Column for y-axis
        row_col: Column for row faceting
        col_col: Column for column faceting
        hue_col: Column for color grouping
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    if row_col and col_col and row_col in df.columns and col_col in df.columns:
        # Create facet grid
        g = sns.FacetGrid(df, row=row_col, col=col_col, hue=hue_col if hue_col else None,
                         margin_titles=True, height=4, aspect=1.2)
        
        g.map_dataframe(sns.scatterplot, x=x_col, y=y_col, s=80)
        g.add_legend()
        g.set_axis_labels(x_col, y_col)
        g.fig.suptitle(title, y=1.02)
        
        fig = g.fig
    else:
        # Simple plot without faceting
        fig, ax = plt.subplots()
        sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_col, ax=ax, s=100)
        ax.set_title(title)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def plot_time_series(df: pd.DataFrame,
                    time_col: str = 'elapsed_time_sec',
                    value_col: str = 'mb_per_sec',
                    group_col: Optional[str] = None,
                    title: str = 'Throughput Over Time',
                    output_path: Optional[str] = None) -> plt.Figure:
    """
    Plot metrics as a time series.
    
    Args:
        df: DataFrame with test metrics
        time_col: Column for time axis
        value_col: Column for value axis
        group_col: Column for grouping
        title: Plot title
        output_path: Optional path to save the figure
        
    Returns:
        Matplotlib figure
    """
    setup_plotting_style()
    
    fig, ax = plt.subplots()
    
    if group_col and group_col in df.columns:
        for group_value in df[group_col].unique():
            subset = df[df[group_col] == group_value].sort_values(time_col)
            ax.plot(subset[time_col], subset[value_col], 
                   label=f'{group_col}={group_value}', linewidth=2)
    else:
        sorted_df = df.sort_values(time_col)
        ax.plot(sorted_df[time_col], sorted_df[value_col], linewidth=2)
    
    ax.set_xlabel('Time (sec)')
    ax.set_ylabel('Throughput (MB/sec)')
    ax.set_title(title)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    return fig


def create_all_plots(producer_df: pd.DataFrame, consumer_df: pd.DataFrame,
                    output_dir: str) -> List[str]:
    """
    Create all standard plots and save to output directory.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        output_dir: Output directory for plots
        
    Returns:
        List of created plot file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    plot_files = []
    
    # Producer plots
    if not producer_df.empty:
        fig1 = plot_throughput_vs_latency(
            producer_df,
            title='Producer: Throughput vs Latency',
            output_path=str(output_path / 'producer_throughput_vs_latency.png')
        )
        plot_files.append(str(output_path / 'producer_throughput_vs_latency.png'))
        plt.close(fig1)
        
        fig2 = plot_latency_percentiles(
            producer_df,
            title='Producer: Latency Percentiles',
            output_path=str(output_path / 'producer_latency_percentiles.png')
        )
        plot_files.append(str(output_path / 'producer_latency_percentiles.png'))
        plt.close(fig2)
        
        fig3 = plot_throughput_efficiency(
            producer_df,
            title='Producer: Throughput Efficiency',
            output_path=str(output_path / 'producer_throughput_efficiency.png')
        )
        plot_files.append(str(output_path / 'producer_throughput_efficiency.png'))
        plt.close(fig3)
    
    # Consumer plots
    if not consumer_df.empty:
        fig4 = plot_consumer_throughput(
            consumer_df,
            title='Consumer: Throughput by Group',
            output_path=str(output_path / 'consumer_throughput.png')
        )
        plot_files.append(str(output_path / 'consumer_throughput.png'))
        plt.close(fig4)
    
    print(f"\nCreated {len(plot_files)} plots in {output_path}")
    
    return plot_files
