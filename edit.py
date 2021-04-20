import csv


with open("flugfeld.csv") as file:
    reader = csv.reader(file, delimiter=",")
    next(reader)
    lines = []
    for row in reader:
        # your multi purpose code here
        lines.append(row)

with open("flugfeld_edited.csv", "w") as file:
    writer = csv.writer(file)
    writer.writerow(["Region", "WeGlide", "OpenAIP" ,"OpenAIP ID", "Launches", "Wrong"])
    writer.writerows(lines)
