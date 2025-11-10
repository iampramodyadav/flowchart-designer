# 📊 Flowchart Designer

A powerful, cross-platform desktop application for designing flowcharts and complex diagrams using the **PyQt5** framework. This tool offers an intuitive graphical interface for creating and connecting shapes, coupled with robust export capabilities utilizing popular visualization libraries like **Mermaid**, **NetworkX** (for static plotting), and **PyVis** (for interactive HTML).

Developed by **Pramod Kumar Yadav**.

## ✨ Features

  * **GUI-based Design:** Drag-and-drop-like interface for adding and moving standard flowchart shapes (**Process**, **Decision**, **Start/End**, **Input/Output**, **Ellipse**).
  * **Real-time Connections:** Easily draw connectors between shapes. Double-click connectors to add labels (e.g., "Yes," "No").
  * **Auto-Layout:** Automatically arrange complex flowcharts into clean, layered structures for improved readability.
  * **Multiple Export Formats:**
      * **Mermaid Code (`.mmd`):** Export the design as clean, portable Mermaid markdown code.
      * **JSON Project (`.json`):** Save and load entire project layouts, including shape positions, sizes, and colors.
      * **Interactive HTML:** Generate a dynamic, physics-based visualization using **PyVis**.
      * **Static Images:** Export high-quality plots using **Matplotlib** and **NetworkX** (PNG/JPG/SVG).
      * **Canvas Export:** Export the exact GUI canvas design as **PNG** or **SVG**.
  * **Customization:** Set custom text and background colors for new shapes.

## 🚀 Getting Started

### Prerequisites

You need **Python 3.x** installed on your system.

This application relies on several external Python libraries, which can be installed via `pip`.

```
pip install PyQt5 PyQtWebEngine networkx matplotlib pyvis
```

### Running the Application

1.  Save the code as `plot_flowchart.py`.
2.  Run the application from your terminal:

<!-- end list -->

```
python plot_flowchart.py
```

The graphical user interface (GUI) will open, ready for you to start designing.

## 👨‍💻 Author Information

| **Role** | **Name** | **Contact** |
| :--- | :--- | :--- |
| Developer | **Pramod Kumar Yadav** | pkyadav01234@gmail.com |
| Copyright | © 2024 Flowchart Designer | |

## 📜 License

This project is licensed under the MIT License
