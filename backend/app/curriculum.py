"""Chemistry syllabus (Classes XI-XII) as a Grade -> Unit -> Topic tree.

Topic IDs look like "XI-01-03" (grade, unit number, topic number) and drive
lesson order, RAG filtering and progress tracking.
"""

# (unit title, periods, [topics])
_XI = [
    ("Some Basic Concepts of Chemistry", 14, [
        "Importance and scope of chemistry",
        "Laws of chemical combination and Dalton's atomic theory",
        "Atomic and molecular masses",
        "Mole concept and molar mass",
        "Percentage composition, empirical and molecular formula",
        "Chemical reactions and stoichiometry",
    ]),
    ("Structure of Atom", 16, [
        "Discovery of electron, proton and neutron",
        "Atomic number, isotopes and isobars",
        "Thomson, Rutherford and Bohr models",
        "Dual nature of matter and de Broglie relationship",
        "Heisenberg uncertainty principle",
        "Orbitals, quantum numbers and shapes of s, p, d orbitals",
        "Aufbau principle, Pauli exclusion principle and Hund's rule",
        "Electronic configuration and stability of half-filled and filled orbitals",
    ]),
    ("Classification of Elements and Periodicity in Properties", 8, [
        "Development of the periodic table and modern periodic law",
        "Atomic, ionic and inert gas radii",
        "Ionization enthalpy and electron gain enthalpy",
        "Electronegativity and valence",
        "Nomenclature of elements with atomic number above 100",
    ]),
    ("Chemical Bonding and Molecular Structure", 16, [
        "Ionic bond and lattice concepts",
        "Covalent bond, Lewis structures and bond parameters",
        "Polarity of covalent bond and covalent character of ionic bond",
        "Valence bond theory and resonance",
        "VSEPR theory and geometry of molecules",
        "Hybridization (s, p, d orbitals)",
        "Molecular orbital theory of homonuclear diatomic molecules",
        "Hydrogen bond",
    ]),
    ("States of Matter: Gases and Liquids", 14, [
        "Intermolecular interactions and types of bonding",
        "Gas laws: Boyle, Charles, Gay-Lussac, Avogadro",
        "Ideal gas equation",
        "Kinetic energy and molecular speeds",
        "Deviation from ideal behaviour, liquefaction and critical temperature",
        "Liquid state: vapour pressure, viscosity and surface tension",
    ]),
    ("Thermodynamics", 18, [
        "System, surroundings, work, heat and state functions",
        "First law: internal energy and enthalpy",
        "Heat capacity and measurement of dU and dH",
        "Hess's law of constant heat summation",
        "Enthalpies of bond dissociation, combustion, formation, atomization and solution",
        "Entropy and the second law",
        "Gibbs energy and spontaneity",
        "Third law of thermodynamics",
    ]),
    ("Equilibrium", 20, [
        "Equilibrium in physical and chemical processes",
        "Law of mass action and equilibrium constant",
        "Le Chatelier's principle",
        "Ionization of acids and bases, strength and pH",
        "Polybasic acids and hydrolysis of salts",
        "Buffer solutions and Henderson equation",
        "Solubility product and common ion effect",
    ]),
    ("Redox Reactions", 6, [
        "Oxidation, reduction and oxidation number",
        "Balancing redox reactions",
        "Applications of redox reactions",
    ]),
    ("Hydrogen", 8, [
        "Position, occurrence and isotopes of hydrogen",
        "Preparation, properties and uses of hydrogen",
        "Hydrides: ionic, covalent and interstitial",
        "Water and heavy water",
        "Hydrogen peroxide",
        "Hydrogen as a fuel",
    ]),
    ("s-Block Elements", 14, [
        "Group 1 and 2: electronic configuration and periodic trends",
        "Anomalous properties and diagonal relationship",
        "Chemical reactivity with oxygen, water, hydrogen and halogens",
        "Sodium carbonate, chloride, hydroxide and hydrogencarbonate",
        "CaO, CaCO3 and industrial use of lime and limestone",
        "Biological importance of Na, K, Mg and Ca",
    ]),
    ("Some p-Block Elements", 16, [
        "General introduction to p-block and Group 13",
        "Boron: borax, boric acid and boron hydrides",
        "Aluminium: uses and reactions with acids and alkalies",
        "Group 14: general trends and anomalous behaviour of carbon",
        "Carbon: catenation, allotropes and oxides",
        "Silicon compounds: silicones, silicates and zeolites",
    ]),
    ("Organic Chemistry: Some Basic Principles and Techniques", 14, [
        "Classification and IUPAC nomenclature of organic compounds",
        "Methods of purification",
        "Qualitative and quantitative analysis",
        "Inductive effect, electromeric effect, resonance and hyperconjugation",
        "Homolytic and heterolytic fission, free radicals, carbocations, carbanions",
        "Electrophiles, nucleophiles and types of organic reactions",
    ]),
    ("Hydrocarbons", 16, [
        "Classification of hydrocarbons",
        "Alkanes: nomenclature, isomerism, conformations and reactions",
        "Alkenes: structure, geometrical isomerism, addition reactions",
        "Alkynes: structure, acidic character and reactions",
        "Aromatic hydrocarbons: benzene, resonance and aromaticity",
        "Electrophilic substitution and directive influence",
    ]),
    ("Environmental Chemistry", 6, [
        "Air pollution, smog and acid rain",
        "Ozone and effects of its depletion",
        "Greenhouse effect and global warming",
        "Water and soil pollution",
        "Green chemistry and pollution control",
    ]),
]

_XII = [
    ("Solid State", 12, [
        "Classification of solids and amorphous vs crystalline",
        "Unit cells and density calculations",
        "Packing in solids, packing efficiency and voids",
        "Point defects",
        "Electrical and magnetic properties; band theory",
    ]),
    ("Solutions", 12, [
        "Types of solutions and expressing concentration",
        "Solubility of gases in liquids",
        "Raoult's law and vapour pressure",
        "Colligative properties",
        "Abnormal molar mass and van't Hoff factor",
    ]),
    ("Electrochemistry", 14, [
        "Conductance, molar conductivity and Kohlrausch's law",
        "Electrolysis and Faraday's laws",
        "Galvanic cells, EMF and standard electrode potential",
        "Nernst equation",
        "Gibbs energy and EMF of a cell",
        "Batteries, fuel cells and corrosion",
    ]),
    ("Chemical Kinetics", 12, [
        "Rate of a reaction and factors affecting it",
        "Order, molecularity and rate law",
        "Integrated rate equations and half-life",
        "Collision theory",
        "Activation energy and Arrhenius equation",
    ]),
    ("Surface Chemistry", 8, [
        "Adsorption: physisorption and chemisorption",
        "Catalysis and enzyme catalysis",
        "Colloids and their properties",
        "Emulsions",
    ]),
    ("General Principles and Processes of Isolation of Elements", 8, [
        "Concentration, oxidation, reduction and refining",
        "Extraction of aluminium, copper, zinc and iron",
    ]),
    ("p-Block Elements", 14, [
        "Group 15: nitrogen and its compounds",
        "Phosphorus and its compounds",
        "Group 16: dioxygen and ozone",
        "Sulphur, sulphur dioxide and sulphuric acid",
        "Group 17: chlorine, HCl and interhalogens",
        "Group 18: noble gases",
    ]),
    ("d and f Block Elements", 14, [
        "Transition metals: electronic configuration and trends",
        "Preparation and properties of K2Cr2O7 and KMnO4",
        "Lanthanoids and lanthanoid contraction",
        "Actinoids",
    ]),
    ("Coordination Compounds", 12, [
        "Werner's theory, ligands and nomenclature",
        "Isomerism in coordination compounds",
        "Bonding: VBT and CFT",
        "Importance of coordination compounds",
    ]),
    ("Haloalkanes and Haloarenes", 12, [
        "Haloalkanes: nomenclature, C-X bond and preparation",
        "Mechanism of substitution reactions",
        "Optical rotation and chirality",
        "Haloarenes",
        "Uses and environmental effects of polyhalogen compounds",
    ]),
    ("Alcohols, Phenols and Ethers", 12, [
        "Alcohols: preparation and properties",
        "Mechanism of dehydration; methanol and ethanol",
        "Phenols: acidic nature and substitution reactions",
        "Ethers",
    ]),
    ("Aldehydes, Ketones and Carboxylic Acids", 12, [
        "Aldehydes and ketones: preparation and properties",
        "Nucleophilic addition and alpha-hydrogen reactivity",
        "Carboxylic acids: acidic nature, preparation, properties",
    ]),
    ("Organic Compounds Containing Nitrogen", 10, [
        "Amines: classification, preparation, properties",
        "Diazonium salts",
    ]),
    ("Biomolecules", 12, [
        "Carbohydrates",
        "Proteins and enzymes",
        "Hormones and vitamins",
        "Nucleic acids: DNA and RNA",
    ]),
    ("Polymers", 8, [
        "Classification and methods of polymerization",
        "Important polymers and biodegradability",
    ]),
    ("Chemistry in Everyday Life", 8, [
        "Chemicals in medicines",
        "Chemicals in food",
        "Cleansing agents: soaps and detergents",
    ]),
]

CURRICULUM = {"XI": _XI, "XII": _XII}


def flatten():
    """Yield one dict per topic, in teaching order."""
    for grade, units in CURRICULUM.items():
        order = 0
        for u_idx, (unit_title, _periods, topics) in enumerate(units, start=1):
            for t_idx, title in enumerate(topics, start=1):
                order += 1
                yield {
                    "id": f"{grade}-{u_idx:02d}-{t_idx:02d}",
                    "grade": grade,
                    "unit_no": u_idx,
                    "unit_title": unit_title,
                    "title": title,
                    "ord": order,
                }


def tree():
    """JSON-friendly tree for the frontend."""
    out = {}
    for grade, units in CURRICULUM.items():
        out[grade] = []
        for u_idx, (unit_title, periods, topics) in enumerate(units, start=1):
            out[grade].append({
                "unit_no": u_idx,
                "title": unit_title,
                "periods": periods,
                "topics": [
                    {"id": f"{grade}-{u_idx:02d}-{t_idx:02d}", "title": t}
                    for t_idx, t in enumerate(topics, start=1)
                ],
            })
    return out
