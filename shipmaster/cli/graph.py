def print_graph(args, project):
    columns = []
    max_rows = 0
    for stage in project.config.stages:
        rows = []
        max_width = 0
        for image in project.config.images.values():
            if image.stage == stage:
                rows.append(image.name)
                max_width = max(max_width, len(image.name))
        max_rows = max(max_rows, len(rows))
        columns.append((stage, max_width, rows))

    def draw_column(col, pre, content, arrow=False):
        if col == 0:
            return " " + pre + content + pre + ("--" if arrow else "  ")
        elif col == len(columns)-1:
            return (">" if arrow else " ") + pre + content + pre
        return (">" if arrow else " ") + pre + content + pre + ("--" if arrow else "  ")

    row1 = row2 = row3 = ""
    for i, col in enumerate(columns):
        stage, width, rows = col
        row1 += draw_column(i, ".", "-"*(width+6))
        row2 += draw_column(i, "|", stage.center(width+6), True)
        row3 += draw_column(i, "|", "-"*(width+6))

    print()
    print(row1)
    print(row2)
    print(row3)

    for row_num in range(max_rows+1):
        row = ""
        for i, col in enumerate(columns):
            stage, width, rows = col
            if len(rows) > row_num:
                row += draw_column(i, "|", " "+rows[row_num].ljust(width+5))
            elif len(rows) == row_num:
                row += draw_column(i, "'", "-"*(width+6))
            else:
                row += draw_column(i, " ", " "*(width+6))
        print(row)
    print()
