with open('Black_Knight_Quant_Reporter.mq5', 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

#1. Update variables declaration block
target_decl = """      double entry_price = 0;
      datetime entry_time = 0;
      double sl = 0;
      long entry_magic = 0;"""

replacement_decl = """      double entry_price = 0;
      datetime entry_time = 0;
      double sl = 0;
      double tp = 0;
      long entry_magic = 0;"""

#2. Update local declaration inside HistorySelectByPosition
target_local = """         if(cumulative_closed_volume > 0)
             export_volume = cumulative_closed_volume;
          
         double tp = 0;
         for(int k=HistoryOrdersTotal()-1; k>=0; k--)"""

replacement_local = """         if(cumulative_closed_volume > 0)
             export_volume = cumulative_closed_volume;
          
         tp = 0;
         for(int k=HistoryOrdersTotal()-1; k>=0; k--)"""

if target_decl in content and target_local in content:
    content = content.replace(target_decl, replacement_decl)
    content = content.replace(target_local, replacement_local)
    with open('Black_Knight_Quant_Reporter.mq5', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success!")
else:
    print("Error: Target strings not found in Black_Knight_Quant_Reporter.mq5!")
