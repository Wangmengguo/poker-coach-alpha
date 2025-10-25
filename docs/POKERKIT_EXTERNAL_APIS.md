# PokerKit 外置接口一览

- 生成时间：2025-10-24 14:54:52
- 说明：根据 `pokerkit/__init__.py` 的 `__all__` 与按模块导入关系自动整理，列出公开接口与其简要说明（取自定义/函数的首行文档字符串）。

## 分析 (analysis)

- calculate_equities: Calculate the equities.
- calculate_hand_strength: Calculate the hand strength: odds of beating a single other hand
- calculate_icm: Calculate the independent chip model (ICM) values.
- parse_range: Parse the range.
- Statistics: The class for player statistics.

## 游戏 (games)

- DeuceToSevenLowballMixin: The abstract base class for deuce-to-seven lowball games.
- Draw: The abstract base class for draw games.
- FixedLimitBadugi: The class for fixed-limit badugi games.
- FixedLimitDeuceToSevenLowballTripleDraw: The class for fixed-limit deuce-to-seven lowball triple draw
- FixedLimitOmahaHoldemHighLowSplitEightOrBetter: The class for fixed-limit Omaha hold'em high/low-split eight or
- FixedLimitPokerMixin: The mixin for fixed-limit poker games.
- FixedLimitRazz: The class for fixed-limit razz games.
- FixedLimitSevenCardStud: The class for fixed-limit seven card stud games.
- FixedLimitSevenCardStudHighLowSplitEightOrBetter: The class for fixed-limit seven card stud high/low-split eight or
- FixedLimitTexasHoldem: The class for fixed-limit Texas hold'em games.
- Holdem: The abstract base class for hold'em games.
- NoLimitDeuceToSevenLowballSingleDraw: The class for no-limit deuce-to-seven lowball single draw games.
- NoLimitPokerMixin: The mixin for no-limit poker games.
- NoLimitRoyalHoldem: The class for no-limit royal hold'em games.
- NoLimitShortDeckHoldem: The class for no-limit short-deck hold'em games.
- NoLimitTexasHoldem: The class for no-limit Texas hold'em games.
- OmahaHoldemMixin: The mixin for Omaha hold'em games.
- Poker: The abstract base class for poker games.
- PotLimitOmahaHoldem: The class for pot-limit Omaha hold'em games.
- PotLimitPokerMixin: The mixin for pot-limit poker games.
- SevenCardStud: The abstract base class for seven card stud games.
- SingleDraw: The abstract base class for single draw games.
- TexasHoldemMixin: The mixin for Texas hold'em games.
- TripleDraw: The abstract base class for triple draw games.
- UnfixedLimitHoldem: The abstract base class for unfixed-limit hold'em games.

## 牌型 (hands)

- BadugiHand: The class for badugi hands (ace-to-five).
- BoardCombinationHand: The abstract base class for board-combination hands.
- CombinationHand: The abstract base class for combination hands.
- EightOrBetterLowHand: The class for eight or better low hands.
- GreekHoldemHand: The class for Greek hold'em hands.
- Hand: The abstract base class for poker hands.
- HoleBoardCombinationHand: The abstract base class for hole-board-combination hands.
- KuhnPokerHand: The class for Kuhn poker hands.
- OmahaEightOrBetterLowHand: The class for Omaha eight or better low hands.
- OmahaHoldemHand: The class for Omaha hold'em hands.
- RegularLowHand: The class for low regular hands.
- ShortDeckHoldemHand: The class for short-deck hold'em hands.
- StandardBadugiHand: The class for standard badugi hands (deuce-to-seven).
- StandardHand: The abstract base class for standard hands.
- StandardHighHand: The class for standard high hands.
- StandardLowHand: The class for standard low hands.

## 查表 (lookups)

- BadugiLookup: The class for badugi hand lookups (ace-to-five).
- EightOrBetterLookup: The class for eight or better hand lookups.
- Entry: The class for hand lookup entries.
- KuhnPokerLookup: The class for Kuhn poker hand lookups.
- Label: The enum class for all hand classification labels.
- Lookup: The abstract base class for hand lookups.
- RegularLookup: The class for regular hand lookups.
- ShortDeckHoldemLookup: The class for short-deck hold'em hand lookups.
- StandardBadugiLookup: The class for standard badugi hand lookups (deuce-to-seven).
- StandardLookup: The class for standard hand lookups.

## 牌谱/解析 (notation)

- AbsolutePokerParser: A class for Absolute Poker hand history parser.
- ACPCProtocolParser: A class for ACPC Protocol hand history parser.
- FullTiltPokerParser: A class for Full Tilt Poker hand history parser.
- HandHistory: The class for hand histories.
- IPokerNetworkParser: A class for iPoker Network hand history parser.
- OngameNetworkParser: A class for Ongame Network hand history parser.
- parse_action: Parse the action.
- Parser: An abstract base class for hand history parser.
- PartyPokerParser: A class for PartyPoker hand history parser.
- PokerStarsParser: A class for PokerStars hand history parser.
- REParser: An abstract base class for hand history parser using regular

## 状态与操作 (state)

- AntePosting: The class for ante postings.
- Automation: The enum class for automations.
- BetCollection: The class for bet collections.
- BettingStructure: The enum class for betting structures.
- BlindOrStraddlePosting: The class for blind or straddle postings.
- BoardDealing: The class for board dealings.
- BringInPosting: The class for bring-in postings.
- CardBurning: The class for card burnings.
- CheckingOrCalling: The class for checking or callings.
- ChipsPulling: The class for chips pullings.
- ChipsPushing: The class for chips pushings.
- CompletionBettingOrRaisingTo: The class for completion, betting, or raising tos.
- Folding: The class for foldings.
- HandKilling: The class for hand killings.
- HoleCardsShowingOrMucking: The class for hole cards showing or muckings.
- HoleDealing: The class for hole dealings.
- Mode: The enum class for poker state types.
- NoOperation: The class for no-operations.
- Opening: The enum class for openings.
- Operation: The abstract base class for operations.
- Pot: The class for pots.
- RunoutCountSelection: The class for runout-count selection.
- StandingPatOrDiscarding: The class for standing pat or discardings.
- State: The class for poker states.
- Street: The class for streets.

## 工具 (utilities)

- Card: The class for cards.
- CardsLike:
- clean_values: Clean the numerical values.
- Deck: The enum class for a tuple of cards representing decks.
- divmod: Divide the amount and get its quotient and remainder.
- filter_none: Filter out ``None`` from an iterable of values.
- max_or_none: Get the maximum value while ignoring ``None`` values.
- min_or_none: Get the minimum value while ignoring ``None`` values.
- parse_month: Convert ``str`` to a month (``int``).
- parse_time: Convert ``str`` to a ``datetime.time``.
- parse_value: Convert ``str`` to a numerical value.
- rake: Rake the amount.
- Rank: The enum class for ranks.
- RankOrder: The enum class for ordering of ranks.
- rotated: Rotate the values.
- shuffled: Return the shuffled values.
- sign: Get sign of a numerical value.
- Suit: The enum class for suits.
- UNMATCHABLE_PATTERN:
- ValuesLike:
