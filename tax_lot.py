import csv
from datetime import datetime, timedelta

MERGE_DATE = "11/22/2023"

# default ratio, can be refined by user input
VMW_SHARES_TO_CASH_RATIO = 0.479
VMW_SHARES_TO_STOCK_RATIO = 0.521

AVGO_FMV = 979.5  # avg of high/low on merge date
ONE_VMW_TO_CASH = 142.5
ONE_VMW_TO_AGVO_SHARE = 0.252

VMW_CASH_COMPONENT_VALUE = VMW_SHARES_TO_CASH_RATIO * ONE_VMW_TO_CASH
VMW_AVGO_SHARE_COMPONENT_RATIO = VMW_SHARES_TO_STOCK_RATIO * ONE_VMW_TO_AGVO_SHARE
VMW_FMV_AFTER_MERGE = VMW_CASH_COMPONENT_VALUE + VMW_AVGO_SHARE_COMPONENT_RATIO * AVGO_FMV

VMW_DIVIDEND_2021_DATE = "11/01/2021"
VMW_DIVIDEND_2021_COST_BASE_REDUCTION = 16.58
VMW_DIVIDEND_2018_DATE = "12/28/2018"
VMW_DIVIDEND_2018_COST_BASE_REDUCTION = 10.18

VMW_PRICE_FILE = "data/vmw-historical-price.csv"
ESPP_DATE_FILE = "data/espp-date.csv"
DAYS_IN_YEAR = 365

merge_date = datetime.strptime(MERGE_DATE, "%m/%d/%Y")
dividend_date_2018 = datetime.strptime(VMW_DIVIDEND_2018_DATE, "%m/%d/%Y")
dividend_date_2021 = datetime.strptime(VMW_DIVIDEND_2021_DATE, "%m/%d/%Y")
stock_prices = {}
espp_dates = {}


# refine vmw share to cash/stock conversion ratio
def update_global_variable(vmw_to_cash_share, vmw_to_avgo_share):
    global VMW_SHARES_TO_CASH_RATIO
    global VMW_SHARES_TO_STOCK_RATIO
    global VMW_CASH_COMPONENT_VALUE
    global VMW_AVGO_SHARE_COMPONENT_RATIO
    global VMW_FMV_AFTER_MERGE

    cash_ratio = vmw_to_cash_share / (vmw_to_cash_share + vmw_to_avgo_share)
    stock_ratio = vmw_to_avgo_share / (vmw_to_cash_share + vmw_to_avgo_share)

    VMW_SHARES_TO_CASH_RATIO = cash_ratio
    VMW_SHARES_TO_STOCK_RATIO = stock_ratio
    VMW_CASH_COMPONENT_VALUE = VMW_SHARES_TO_CASH_RATIO * ONE_VMW_TO_CASH
    VMW_AVGO_SHARE_COMPONENT_RATIO = VMW_SHARES_TO_STOCK_RATIO * ONE_VMW_TO_AGVO_SHARE
    VMW_FMV_AFTER_MERGE = VMW_CASH_COMPONENT_VALUE + VMW_AVGO_SHARE_COMPONENT_RATIO * AVGO_FMV


def display_global_variable(output_file):
    output_file.write('{:<35s}${:,.2f}\n'.format("AVGO FMV (%s):" % MERGE_DATE, AVGO_FMV))
    output_file.write('{:<35s}${:,.6f}\n'.format("VMW per share cash value:", VMW_CASH_COMPONENT_VALUE))
    output_file.write('{:<35s}{:<.6f}\n'.format("VMW per share AVGO ratio:", VMW_AVGO_SHARE_COMPONENT_RATIO))
    output_file.write('{:<35s}${:,.6f}\n'.format("VMW per share value after merge:", VMW_FMV_AFTER_MERGE))
    output_file.write('{:<35s}{:,.6f}\n'.format("VMW shares to cash percent:", VMW_SHARES_TO_CASH_RATIO))
    output_file.write('{:<35s}{:,.6f}\n\n'.format("VMW shares to stock percent:", VMW_SHARES_TO_STOCK_RATIO))

    output_file.write("VMW Special dividends:\n")
    output_file.write("    {} return of capital: ${:.2f}\n".format(VMW_DIVIDEND_2018_DATE, VMW_DIVIDEND_2018_COST_BASE_REDUCTION))
    output_file.write("    {} return of capital: ${:.2f}\n\n".format(VMW_DIVIDEND_2021_DATE, VMW_DIVIDEND_2021_COST_BASE_REDUCTION))

    output_file.write("Note: VMW shares held on the date of either/both special dividend(s) will have their cost basis\n"
                      "      reduced by the amount of the return of capital of either/both special dividend(s).\n\n")

def load_historical_price():
    with open(VMW_PRICE_FILE) as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for row in csvreader:
            stock_prices[row[0]] = row[4]


def load_espp_dates():
    with open(ESPP_DATE_FILE) as csvfile:
        csvreader = csv.reader(csvfile, delimiter=',')
        for row in csvreader:
            espp_dates[row[0]] = row[1]


def get_stock_price(date_str):
    # when date not found in dictionary, lookup previous days
    while date_str not in stock_prices:
        date = datetime.strptime(date_str, "%m/%d/%Y")
        date = date - timedelta(days=1)
        date_str = date.strftime("%m/%d/%Y")

    return float(stock_prices[date_str])


def get_espp_offer_date(date_str):
    if date_str in espp_dates:
        return espp_dates[date_str]
    else:
        return None


def populate_espp_data(lot):
    acquire_date_str = lot["acquire_date"]

    # lookup offer date
    offer_date_str = get_espp_offer_date(acquire_date_str)

    offer_date_fmv = get_stock_price(offer_date_str)
    acquire_date_fmv = get_stock_price(acquire_date_str)
    min_price = min(offer_date_fmv, acquire_date_fmv)
    purchase_price = min_price * 0.85

    lot["offer_date"] = offer_date_str
    lot["offer_date_fmv"] = offer_date_fmv
    lot["acquire_date_fmv"] = acquire_date_fmv
    lot["purchase_price"] = purchase_price


def is_qualifying_disposition(offer_date, acquire_date, sold_date, force_qualifying_disposition):
    status = ((sold_date - acquire_date).days > DAYS_IN_YEAR) and ((sold_date - offer_date).days > DAYS_IN_YEAR * 2)

    if force_qualifying_disposition and not status:
        print("Force ESPP lot to use qualifying disposition, acquire_date=%s" % acquire_date)
        return True

    return status


def calc_espp_cost_base(lot, force_qualifying_disposition):
    populate_espp_data(lot)

    offer_date = datetime.strptime(lot["offer_date"], "%m/%d/%Y")
    acquire_date = datetime.strptime(lot["acquire_date"], "%m/%d/%Y")
    sold_date = datetime.strptime(lot["sold_date"], "%m/%d/%Y")

    # calc tax
    if is_qualifying_disposition(offer_date, acquire_date, sold_date, force_qualifying_disposition):
        lot["qualifying_disposition"] = True
        offer_date_discount = lot["offer_date_fmv"] * 0.15

        # gain can be determined only after lot avgo shares are sold. For all existing espp lots, the bargain
        # element is 15% of offer day price unless future sold avgo share price is lower than $600 per share,
        # in which case, we need to replace VMW_FMV_AFTER_MERGE to avgo sold price
        gain = VMW_FMV_AFTER_MERGE - lot["purchase_price"]

        ordinary_income = max(min(offer_date_discount, gain), 0)
    else:
        lot["qualifying_disposition"] = False
        ordinary_income = lot["acquire_date_fmv"] - lot["purchase_price"]

    lot["ordinary_income"] = ordinary_income
    lot["total_ordinary_income"] = lot["ordinary_income"] * lot["share"]
    lot["cost_base"] = lot["purchase_price"]

    return lot


def calc_cost_base(lot):
    if "purchase_price" in lot:
        lot["acquire_date_fmv"] = lot["purchase_price"]
        lot["cost_base"] = lot["purchase_price"]
    else:
        acquire_date_fmv = get_stock_price(lot["acquire_date"])
        lot["acquire_date_fmv"] = acquire_date_fmv
        lot["purchase_price"] = acquire_date_fmv
        lot["cost_base"] = acquire_date_fmv

    # already included in w2 if applicable
    lot["ordinary_income"] = 0
    lot["total_ordinary_income"] = 0

    return lot


def adjust_special_dividend(lot):
    cost_base = lot["cost_base"]
    acquire_date_str = lot["acquire_date"]

    acquire_date = datetime.strptime(acquire_date_str, "%m/%d/%Y")
    delta2018 = dividend_date_2018 - acquire_date
    delta2021 = dividend_date_2021 - acquire_date

    if delta2018.days > 0:
        lot["cost_base"] = cost_base - (VMW_DIVIDEND_2018_COST_BASE_REDUCTION + VMW_DIVIDEND_2021_COST_BASE_REDUCTION)
    elif delta2021.days > 0:
        lot["cost_base"] = cost_base - VMW_DIVIDEND_2021_COST_BASE_REDUCTION


def calc_merge_tax_and_avgo_cost_base(lot):
    cost_base = lot["cost_base"]

    merge_gain = VMW_FMV_AFTER_MERGE - cost_base
    lot["merge_gain"] = merge_gain
    capital_gain = max(min(merge_gain, VMW_CASH_COMPONENT_VALUE), 0)
    lot["capital_gain"] = capital_gain
    lot["total_capital_gain"] = lot["capital_gain"] * lot["share"]

    if merge_gain >= VMW_CASH_COMPONENT_VALUE:
        filing_cost_base = 0
    else:
        filing_cost_base = (VMW_CASH_COMPONENT_VALUE - capital_gain) * lot["share"]

    lot["filing_cost_base"] = filing_cost_base

    avgo_cost_base = (cost_base + capital_gain - VMW_CASH_COMPONENT_VALUE + lot[
        "ordinary_income"]) / VMW_AVGO_SHARE_COMPONENT_RATIO
    lot["avgo_cost_base"] = avgo_cost_base

    lot["avgo_share"] = VMW_AVGO_SHARE_COMPONENT_RATIO * lot["share"]

    # round to 3 decimal point to match precision used by financial institute
    lot["avgo_total_cost_base"] = round(lot["avgo_cost_base"], 3) * round(lot["avgo_share"], 3)


# calc tax for lot sold before merge
def calc_not_merged_tax(lot):
    lot["filing_cost_base"] = lot["cost_base"] * lot["share"] + lot["total_ordinary_income"]
    lot["total_capital_gain"] = lot["total_proceeds"] - lot["filing_cost_base"]


def set_capital_gain_term(lot):
    acquire_date_str = lot["acquire_date"]
    sold_date_str = lot["sold_date"]

    acquire_date = datetime.strptime(acquire_date_str, "%m/%d/%Y")
    sold_date = datetime.strptime(sold_date_str, "%m/%d/%Y")

    lot["long_term"] = (sold_date - acquire_date).days > DAYS_IN_YEAR


def set_lot_merge_status(lot):
    sold_date_str = lot["sold_date"]
    sold_date = datetime.strptime(sold_date_str, "%m/%d/%Y")

    lot["merged"] = sold_date >= merge_date


def calc_fractional_share(lot):
    lot["fractional_share_cost_base"] = lot["avgo_cost_base"] * lot["fractional_share"]
    lot["fractional_share_capital_gain"] = lot["fractional_share_proceeds"] - lot["fractional_share_cost_base"]

    lot["avgo_share"] = lot["avgo_share"] - lot["fractional_share"]
    lot["avgo_total_cost_base"] = lot["avgo_total_cost_base"] - lot["fractional_share_cost_base"]


def display_lot_tax(lot, output_file, csv_file):
    csv_file.write("{:d},".format(lot["row_id"]))

    output_file.write('{:<35s}{:<s}\n'.format("type:", lot["type"]))
    csv_file.write("{:s},".format(lot["type"]))

    output_file.write('{:<35s}{:<.3f}\n'.format("share:", lot["share"]))
    csv_file.write("{:.3f},".format(lot["share"]))

    output_file.write('{:<35s}{:<s}\n'.format("acquire date:", lot["acquire_date"]))
    csv_file.write("{:s},".format(lot["acquire_date"]))

    output_file.write('{:<35s}{:<s}\n'.format("merge or sold date:", lot["sold_date"]))
    csv_file.write("{:s},".format(lot["sold_date"]))

    output_file.write('{:<35s}{:<s}\n'.format("long term:", str(lot["long_term"])))
    csv_file.write("{:s},".format(str(lot["long_term"])))

    output_file.write('{:<35s}${:,.2f}\n'.format("Box 1d Proceeds:", lot["total_proceeds"]))
    csv_file.write("\"${:,.2f} \",".format(lot["total_proceeds"]))

    output_file.write('{:<35s}${:,.2f}\n'.format("Filing Cost Basis:", lot["filing_cost_base"]))
    csv_file.write("\"${:,.2f} \",".format(lot["filing_cost_base"]))

    output_file.write('{:<35s}${:,.2f}\n'.format("Total Capital Gain:", lot["total_capital_gain"]))
    csv_file.write("\"${:,.2f} \",".format(lot["total_capital_gain"]))

    if lot["type"] == "ESPP":
        output_file.write(
            '{:<35s}${:,.2f}\n'.format("total pending ordinary income:", lot["total_ordinary_income"]))
        csv_file.write("\"${:,.2f} \",".format(lot["total_ordinary_income"]))
    else:
        csv_file.write(",")

    if lot["merged"]:
        output_file.write('{:<35s}{:<.3f}\n'.format("avgo share:", lot["avgo_share"]))
        csv_file.write("{:.3f},".format(lot["avgo_share"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("total avgo cost basis:", lot["avgo_total_cost_base"]))
        csv_file.write("\"${:,.2f} \",".format(lot["avgo_total_cost_base"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("per share avgo cost basis:", lot["avgo_cost_base"]))
        csv_file.write("\"${:,.2f} \",".format(lot["avgo_cost_base"]))
    else:
        csv_file.write(",,,")

    if "fractional_share_cost_base" in lot:
        display_fractional_share(output_file, lot)

    output_file.write("\nper share info:\n")

    output_file.write('{:<35s}${:,.2f}\n'.format("purchase price:", lot["purchase_price"]))
    csv_file.write("\"${:,.2f} \",".format(lot["purchase_price"]))

    output_file.write('{:<35s}${:,.2f}\n'.format("cost basis:", lot["cost_base"]))
    csv_file.write("\"${:,.2f} \",".format(lot["cost_base"]))

    if lot["merged"]:
        output_file.write('{:<35s}${:,.2f}\n'.format("merge gain:", lot["merge_gain"]))
        csv_file.write("\"${:,.2f} \",".format(lot["merge_gain"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("capital gain:", lot["capital_gain"]))
        csv_file.write("\"${:,.2f} \",".format(lot["capital_gain"]))
    else:
        csv_file.write(",,")

    if lot["type"] == "ESPP":
        output_file.write('{:<35s}{:<s}\n'.format("offer date:", lot["offer_date"]))
        csv_file.write("{:s},".format(lot["offer_date"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("offer date fmv:", lot["offer_date_fmv"]))
        csv_file.write("\"${:,.2f} \",".format(lot["offer_date_fmv"]))

        output_file.write('{:<35s}{:<s}\n'.format("acquire date:", lot["acquire_date"]))
        csv_file.write("{:s},".format(lot["acquire_date"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("acquire date fmv:", lot["acquire_date_fmv"]))
        csv_file.write("\"${:,.2f} \",".format(lot["acquire_date_fmv"]))

        output_file.write('{:<35s}{:<s}\n'.format("qualifying disposition:", str(lot["qualifying_disposition"])))
        csv_file.write("{:s},".format(str(lot["qualifying_disposition"])))

        output_file.write('{:<35s}${:,.2f}\n'.format("ordinary income:", lot["ordinary_income"]))
        csv_file.write("\"${:,.2f} \"".format(lot["ordinary_income"]))
    else:
        csv_file.write(",,")

        output_file.write('{:<35s}{:<s}\n'.format("acquire date:", lot["acquire_date"]))
        csv_file.write("{:s},".format(lot["acquire_date"]))

        output_file.write('{:<35s}${:,.2f}\n'.format("acquire date fmv:", lot["acquire_date_fmv"]))
        csv_file.write("\"${:,.2f} \",".format(lot["acquire_date_fmv"]))

        csv_file.write(",")

    csv_file.write("\n")


def generate_csv_header(csv_file):
    csv_file.write("row id,type,share,acquire date,merge or sold date,long term,Box 1d Proceeds,Filing Cost Basis,"
                   "total capital gain,total pending ordinary income,avgo share,total avgo cost basis,"
                   "per share avgo cost base,per share purchase price,per share cost basis,per share merge gain,"
                   "per share capital gain,espp offer date,espp offer data fmv,acquire date,acquire date fmv,"
                   "qualifying disposition,per share ordinary income\n")


def display_fractional_share(output_file, lot):
    output_file.write('\n{:<35s}{:<.3f}\n'.format("fractional share:", lot["fractional_share"]))
    output_file.write('{:<35s}${:,.2f}\n'.format("fractional share proceeds:", lot["fractional_share_proceeds"]))
    output_file.write('{:<35s}${:,.2f}\n'.format("fractional share cost basis:", lot["fractional_share_cost_base"]))
    output_file.write('{:<35s}${:,.2f}\n'.format("fractional share capital gain:",
                                                 lot["fractional_share_capital_gain"]))
