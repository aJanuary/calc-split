import argparse
import csv
import json
import sys

from pulp import (
    PULP_CBC_CMD,
    LpInteger,
    LpMinimize,
    LpProblem,
    LpStatusOptimal,
    LpVariable,
)

SMALL_O = 0.00001


def print_csv(transactions):
    """Format the transactions as a CSV string."""
    writer = csv.writer(sys.stdout)
    for from_person, to_person, amount in transactions:
        writer.writerow([from_person, to_person, amount])
    sys.stdout.flush()


def print_dot(transactions):
    """Prints the transactions in DOT format for Graphviz."""
    print("digraph G {")
    print('  graph [rankdir="TB"]')
    for from_person, to_person, amount in transactions:
        print(f'  "{from_person}" -> "{to_person}" [label="{amount}"]')
    print("}")


def print_json(transactions):
    """Prints the transactions in JSON format."""
    output = []
    for from_person, to_person, amount in transactions:
        output.append({"from": from_person, "to": to_person, "amount": amount})

    print(json.dumps(output, indent=2))


def print_text(transactions):
    """Prints the transactions in a human-readable format."""
    errors = []

    for from_person, to_person, amount in transactions:
        if from_person == "rounding error":
            errors.append(f"{to_person} overpays by {amount}")
        elif to_person == "rounding error":
            errors.append(f"{from_person} underpays by {amount}")
        else:
            print(f"{from_person} pays {to_person} {amount}")

    if len(errors) > 0:
        print()
        for error in errors:
            print(error)


PRINTERS = {
    "csv": print_csv,
    "dot": print_dot,
    "json": print_json,
    "text": print_text,
}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="calc-split",
        description="Calculate who pays who",
    )
    parser.add_argument("infile", type=argparse.FileType("r"), help="input JSON file")
    parser.add_argument(
        "--format",
        choices=PRINTERS.keys(),
        default="text",
        help="format of the output",
    )

    return parser.parse_args()


def parse_infile(infile):
    """Parse the input file and return the balances."""
    data = csv.reader(infile)
    people = {person: int(currency.replace(".", "")) for person, currency in data}

    # There can be rounding errors in the balances.
    # Add a variable to represent the total error so that the problem is solvable.
    people["rounding error"] = -sum(x for x in people.values())
    return people


def solve(people):
    """Solve the optimization problem to find who pays who."""

    problem = LpProblem("who_pays_who", LpMinimize)

    who_pays_who_vars = {}
    amount_vars = {}

    for person_a in people.keys():
        for person_b in people.keys():
            if person_a == person_b:
                continue

            who_pays_who_var = LpVariable(
                f"who_{person_a}_{person_b}",
                lowBound=0,
                upBound=1,
                cat=LpInteger,
            )

            who_pays_who_vars[(person_a, person_b)] = who_pays_who_var

            amount_var = LpVariable(
                f"amount_{person_a}_{person_b}",
                lowBound=0,
                upBound=None,
                cat=LpInteger,
            )

            amount_vars[(person_a, person_b)] = amount_var

            problem += who_pays_who_var >= amount_var * SMALL_O

    for person, amount in people.items():
        this_person_amount_vars = [
            var
            for var_key, var in amount_vars.items()
            if (amount < 0 and var_key[0] == person)
            or (amount > 0 and var_key[1] == person)
        ]

        problem += sum(this_person_amount_vars) == abs(amount)

    problem.objective = sum(who_pays_who_vars.values())

    status = problem.solve(PULP_CBC_CMD(msg=0))
    assert status == LpStatusOptimal

    return [
        (from_person, to_person, format_amount(amount_var.varValue))
        for (from_person, to_person), amount_var in amount_vars.items()
        if amount_var.varValue > 0
    ]


def format_amount(amount):
    """Format the amount as a string with two decimal places."""
    pounds = int(amount) // 100
    pence = int(amount) % 100
    return f"{pounds}.{pence:02d}"


def main():
    """Main function to parse arguments and calculate who pays who."""
    args = parse_args()
    people = parse_infile(args.infile)
    transactions = solve(people)
    PRINTERS[args.format](transactions)


if __name__ == "__main__":
    main()
